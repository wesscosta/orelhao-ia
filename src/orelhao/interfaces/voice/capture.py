from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
import json
import shutil
import signal
from pathlib import Path
import subprocess
import time
import sys
import tempfile
from typing import Callable, Protocol

from orelhao.config import AudioConfig
from orelhao.interfaces.voice.audio import PCM16Audio
from orelhao.interfaces.voice.devices import native_sample_rate, resolve_device
from orelhao.interfaces.voice.resample import resample_pcm16
from orelhao.interfaces.voice.vad import (
    AdaptiveEnergyVAD,
    EnergyVAD,
    SpeechGate,
    SpeechGateState,
    HysteresisSpeechGate,
    WebRTCVAD,
)


class AudioCapture(Protocol):
    last_diagnostics: "CaptureDiagnostics | None"

    def capture(self) -> PCM16Audio: ...


@dataclass(frozen=True, slots=True)
class CaptureDiagnostics:
    hardware_rate: int
    pipeline_rate: int
    noise_floor: float
    speech_threshold: float
    speech_detected: bool
    stop_reason: str
    overflow_count: int = 0
    false_starts: int = 0
    peak_rms: float = 0.0


@dataclass(slots=True)
class MockAudioCapture:
    sample_rate: int = 16_000
    last_diagnostics: CaptureDiagnostics | None = None

    def capture(self) -> PCM16Audio:
        return PCM16Audio(data=b"\x00\x00" * 1600, sample_rate=self.sample_rate, channels=1)


class SoundDeviceAudioCapture:
    """Captura nativa com VAD adaptativo e gate temporal de fala."""

    def __init__(self, config: AudioConfig) -> None:
        self.config = config
        self.last_diagnostics: CaptureDiagnostics | None = None

    def capture(self, on_ready: Callable[[], None] | None = None) -> PCM16Audio:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError(
                "Suporte de áudio não instalado. Execute: pip install -e '.[audio]'"
            ) from exc

        cfg = self.config
        resolved_device = resolve_device(sd, cfg.input_device, "input")
        hardware_rate = native_sample_rate(sd, resolved_device, "input")
        frames_per_block = max(1, int(hardware_rate * cfg.block_ms / 1000))
        pre_roll_blocks = max(1, cfg.pre_roll_ms // cfg.block_ms)
        calibration_blocks = max(1, cfg.vad_calibration_ms // cfg.block_ms)
        speech_start_blocks = max(1, int(cfg.speech_start_timeout_seconds * 1000 / cfg.block_ms))
        max_blocks = max(1, int(cfg.max_record_seconds * 1000 / cfg.block_ms))

        gate = HysteresisSpeechGate(
            start_window_blocks=max(1, cfg.vad_start_window_ms // cfg.block_ms),
            start_ratio=cfg.vad_start_ratio,
            min_voiced_blocks=max(1, cfg.min_speech_ms // cfg.block_ms),
            end_window_blocks=max(1, cfg.vad_end_window_ms // cfg.block_ms),
            end_ratio=cfg.vad_end_ratio,
        )
        speech_vad = WebRTCVAD(cfg.vad_aggressiveness)
        adaptive_vad = AdaptiveEnergyVAD(
            threshold_multiplier=cfg.vad_threshold_multiplier,
            min_threshold=cfg.vad_min_threshold,
            max_threshold=cfg.vad_max_threshold,
        )
        fixed_vad = EnergyVAD(cfg.rms_threshold)

        calibration: list[bytes] = []
        pre_roll: deque[bytes] = deque(maxlen=pre_roll_blocks)
        recorded: list[bytes] = []
        blocks_waiting_for_speech = 0
        overflow_count = 0
        false_starts = 0
        stop_reason = "max_duration"
        ever_started = False
        peak_rms = 0.0

        try:
            stream_context = sd.RawInputStream(
                samplerate=hardware_rate,
                blocksize=frames_per_block,
                device=resolved_device,
                channels=cfg.channels,
                dtype="int16",
            )
        except Exception as exc:
            raise RuntimeError(
                f"Não foi possível abrir a entrada de áudio {cfg.input_device!r} "
                f"em {hardware_rate} Hz: {exc}"
            ) from exc

        with stream_context as stream:
            for _ in range(calibration_blocks):
                raw, overflowed = stream.read(frames_per_block)
                overflow_count += int(bool(overflowed))
                calibration.append(bytes(raw))

            if cfg.adaptive_vad:
                threshold = adaptive_vad.calibrate(calibration)
                vad = adaptive_vad
                noise_floor = adaptive_vad.noise_floor
            else:
                threshold = fixed_vad.rms_threshold
                vad = fixed_vad
                noise_floor = 0.0

            if on_ready is not None:
                on_ready()

            for _ in range(max_blocks):
                raw, overflowed = stream.read(frames_per_block)
                overflow_count += int(bool(overflowed))
                block = bytes(raw)
                block_rms = EnergyVAD.rms(block)
                peak_rms = max(peak_rms, block_rms)
                is_speech = speech_vad.is_speech(block, hardware_rate)
                event = gate.observe(is_speech)

                if gate.state is SpeechGateState.WAITING:
                    blocks_waiting_for_speech += 1
                    pre_roll.append(block)
                    if blocks_waiting_for_speech >= speech_start_blocks:
                        stop_reason = "speech_start_timeout"
                        break
                    continue

                if event == "speech_started":
                    ever_started = True
                    recorded.extend(pre_roll)
                    pre_roll.clear()
                    recorded.append(block)
                    continue

                if gate.state is SpeechGateState.SPEAKING:
                    recorded.append(block)
                    continue

                if event == "speech_ended" or gate.state is SpeechGateState.COMPLETE:
                    recorded.append(block)
                    for _ in range(max(0, cfg.vad_post_roll_ms // cfg.block_ms)):
                        raw, overflowed = stream.read(frames_per_block)
                        overflow_count += int(bool(overflowed))
                        recorded.append(bytes(raw))
                    stop_reason = "silence"
                    break

        speech_detected = gate.state is SpeechGateState.COMPLETE or (
            ever_started and gate.voiced_blocks >= gate.min_voiced_blocks
        )
        self.last_diagnostics = CaptureDiagnostics(
            hardware_rate=hardware_rate,
            pipeline_rate=cfg.sample_rate,
            noise_floor=noise_floor,
            speech_threshold=threshold,
            speech_detected=speech_detected,
            stop_reason=stop_reason,
            overflow_count=overflow_count,
            false_starts=false_starts,
            peak_rms=peak_rms,
        )

        if not speech_detected:
            return PCM16Audio(data=b"", sample_rate=cfg.sample_rate, channels=cfg.channels)

        native_audio = PCM16Audio(
            data=b"".join(recorded),
            sample_rate=hardware_rate,
            channels=cfg.channels,
        )
        return resample_pcm16(native_audio, cfg.sample_rate)


class PipeWireAudioCapture:
    """Captura de voz via ``pw-record`` sem PortAudio no caminho crítico.

    O PipeWire entrega PCM16 mono já na taxa do pipeline. O processo ``pw-record``
    é externo ao Python, então problemas nativos do driver/servidor de áudio não
    corrompem o heap da aplicação. O VAD continua no processo principal para
    preservar a lógica e as métricas do Orelhão IA.
    """

    def __init__(self, config: AudioConfig) -> None:
        self.config = config
        self.last_diagnostics: CaptureDiagnostics | None = None

    def _command(self, output_path: Path) -> list[str]:
        executable = shutil.which(self.config.pipewire_executable)
        if executable is None:
            raise RuntimeError(
                f"PipeWire recorder não encontrado no PATH: {self.config.pipewire_executable!r}"
            )
        cmd = [
            executable,
            f"--rate={self.config.sample_rate}",
            f"--channels={self.config.channels}",
            "--format=s16",
            f"--latency={max(10, self.config.block_ms)}ms",
        ]
        if self.config.channels == 1:
            cmd.append("--channel-map=mono")
        if self.config.pipewire_target:
            cmd.append(f"--target={self.config.pipewire_target}")
        # pw-record mostrou-se mais estável gravando em arquivo RAW real do que
        # escrevendo PCM em stdout. O arquivo é temporário e lido incrementalmente
        # pelo VAD enquanto a gravação continua.
        cmd.append(str(output_path))
        return cmd

    @staticmethod
    def _read_exact_file(stream, size: int, proc: subprocess.Popen[bytes], timeout: float) -> bytes:
        chunks: list[bytes] = []
        remaining = size
        deadline = time.monotonic() + timeout
        while remaining > 0:
            chunk = stream.read(remaining)
            if chunk:
                chunks.append(chunk)
                remaining -= len(chunk)
                continue
            if proc.poll() is not None:
                break
            if time.monotonic() >= deadline:
                break
            time.sleep(0.005)
        return b"".join(chunks)

    def capture(self) -> PCM16Audio:
        cfg = self.config
        frames_per_block = max(1, int(cfg.sample_rate * cfg.block_ms / 1000))
        bytes_per_block = frames_per_block * cfg.channels * 2
        pre_roll_blocks = max(1, cfg.pre_roll_ms // cfg.block_ms)
        calibration_blocks = max(1, cfg.vad_calibration_ms // cfg.block_ms)
        speech_start_blocks = max(
            1, int(cfg.speech_start_timeout_seconds * 1000 / cfg.block_ms)
        )
        max_blocks = max(1, int(cfg.max_record_seconds * 1000 / cfg.block_ms))

        gate = HysteresisSpeechGate(
            start_window_blocks=max(1, cfg.vad_start_window_ms // cfg.block_ms),
            start_ratio=cfg.vad_start_ratio,
            min_voiced_blocks=max(1, cfg.min_speech_ms // cfg.block_ms),
            end_window_blocks=max(1, cfg.vad_end_window_ms // cfg.block_ms),
            end_ratio=cfg.vad_end_ratio,
        )
        speech_vad = WebRTCVAD(cfg.vad_aggressiveness)
        adaptive_vad = AdaptiveEnergyVAD(
            threshold_multiplier=cfg.vad_threshold_multiplier,
            min_threshold=cfg.vad_min_threshold,
            max_threshold=cfg.vad_max_threshold,
        )
        fixed_vad = EnergyVAD(cfg.rms_threshold)

        temp_dir = tempfile.TemporaryDirectory(prefix="orelhao-pw-record-")
        raw_path = Path(temp_dir.name) / "capture.raw"
        proc = subprocess.Popen(
            self._command(raw_path),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            bufsize=0,
        )

        # Aguarda o pw-record criar o arquivo e começar a alimentar o stream.
        startup_deadline = time.monotonic() + 3.0
        while not raw_path.exists() and proc.poll() is None and time.monotonic() < startup_deadline:
            time.sleep(0.01)
        if not raw_path.exists():
            detail = b""
            if proc.stderr is not None:
                detail = proc.stderr.read() or b""
            temp_dir.cleanup()
            raise RuntimeError(
                "pw-record não criou o arquivo temporário de captura: "
                + detail.decode("utf-8", errors="replace").strip()
            )

        raw_stream = raw_path.open("rb", buffering=0)

        calibration: list[bytes] = []
        pre_roll: deque[bytes] = deque(maxlen=pre_roll_blocks)
        recorded: list[bytes] = []
        blocks_waiting_for_speech = 0
        false_starts = 0
        stop_reason = "max_duration"
        ever_started = False
        peak_rms = 0.0

        intentional_stop = False
        process_failed_during_capture = False

        try:
            for _ in range(calibration_blocks):
                block = self._read_exact_file(raw_stream, bytes_per_block, proc, timeout=1.0)
                if len(block) != bytes_per_block:
                    if proc.poll() is not None:
                        process_failed_during_capture = True
                    raise RuntimeError("pw-record encerrou durante a calibração")
                calibration.append(block)

            if cfg.adaptive_vad:
                threshold = adaptive_vad.calibrate(calibration)
                vad = adaptive_vad
                noise_floor = adaptive_vad.noise_floor
            else:
                threshold = fixed_vad.rms_threshold
                vad = fixed_vad
                noise_floor = 0.0

            print("Pode falar agora.", flush=True)

            for _ in range(max_blocks):
                block = self._read_exact_file(raw_stream, bytes_per_block, proc, timeout=1.0)
                if len(block) != bytes_per_block:
                    if proc.poll() is not None:
                        process_failed_during_capture = True
                        stop_reason = "capture_ended"
                        break
                    continue

                block_rms = EnergyVAD.rms(block)
                peak_rms = max(peak_rms, block_rms)
                is_speech = speech_vad.is_speech(block, cfg.sample_rate)
                event = gate.observe(is_speech)

                if gate.state is SpeechGateState.WAITING:
                    blocks_waiting_for_speech += 1
                    pre_roll.append(block)
                    if blocks_waiting_for_speech >= speech_start_blocks:
                        stop_reason = "speech_start_timeout"
                        break
                    continue

                if event == "speech_started":
                    ever_started = True
                    recorded.extend(pre_roll)
                    pre_roll.clear()
                    recorded.append(block)
                    continue

                if gate.state is SpeechGateState.SPEAKING:
                    recorded.append(block)
                    continue

                if event == "speech_ended" or gate.state is SpeechGateState.COMPLETE:
                    recorded.append(block)
                    for _ in range(max(0, cfg.vad_post_roll_ms // cfg.block_ms)):
                        tail = self._read_exact_file(
                            raw_stream, bytes_per_block, proc, timeout=1.0
                        )
                        if len(tail) != bytes_per_block:
                            break
                        recorded.append(tail)
                    stop_reason = "silence"
                    break
        finally:
            raw_stream.close()
            if proc.poll() is None:
                # Encerramento normal solicitado pela aplicação após silêncio,
                # timeout ou duração máxima. SIGINT reproduz o Ctrl+C usado nos
                # testes manuais e permite ao pw-record finalizar o arquivo.
                intentional_stop = True
                proc.send_signal(signal.SIGINT)
                try:
                    proc.wait(timeout=1.5)
                except subprocess.TimeoutExpired:
                    proc.terminate()
                    try:
                        proc.wait(timeout=1.0)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=1.0)

        stderr = b""
        if proc.stderr is not None:
            try:
                stderr = proc.stderr.read() or b""
            except Exception:
                stderr = b""
        temp_dir.cleanup()

        # O pw-record pode retornar código não-zero ao receber o sinal usado para
        # encerrar uma captura válida. Isso não é falha. Só promovemos a erro
        # quando o processo termina inesperadamente por conta própria.
        if process_failed_during_capture and not intentional_stop:
            detail = stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(
                f"Falha no pw-record (código {proc.returncode}): {detail or 'sem detalhes'}"
            )

        speech_detected = gate.state is SpeechGateState.COMPLETE or (
            ever_started and gate.voiced_blocks >= gate.min_voiced_blocks
        )
        self.last_diagnostics = CaptureDiagnostics(
            hardware_rate=cfg.sample_rate,
            pipeline_rate=cfg.sample_rate,
            noise_floor=noise_floor,
            speech_threshold=threshold,
            speech_detected=speech_detected,
            stop_reason=stop_reason,
            overflow_count=0,
            false_starts=false_starts,
            peak_rms=peak_rms,
        )
        if not speech_detected:
            return PCM16Audio(data=b"", sample_rate=cfg.sample_rate, channels=cfg.channels)
        return PCM16Audio(
            data=b"".join(recorded),
            sample_rate=cfg.sample_rate,
            channels=cfg.channels,
        )


class ProcessIsolatedAudioCapture:
    """Executa PortAudio em processo filho para proteger o processo principal.

    Se ALSA/PortAudio abortar por corrupção nativa, a sessão recebe um erro
    controlado e o serviço principal permanece vivo.
    """

    READY_SENTINEL = "ORELHAO_CAPTURE_READY"

    def __init__(self, config: AudioConfig) -> None:
        self.config = config
        self.last_diagnostics: CaptureDiagnostics | None = None

    def capture(self) -> PCM16Audio:
        with tempfile.TemporaryDirectory(prefix="orelhao-capture-") as tmp:
            root = Path(tmp)
            cfg_path = root / "audio-config.json"
            wav_path = root / "capture.wav"
            diag_path = root / "diagnostics.json"
            cfg_path.write_text(self.config.model_dump_json(), encoding="utf-8")
            cmd = [
                sys.executable,
                "-m",
                "orelhao.interfaces.voice.capture_worker",
                "--config",
                str(cfg_path),
                "--wav",
                str(wav_path),
                "--diagnostics",
                str(diag_path),
            ]
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            assert proc.stdout is not None
            first_line = proc.stdout.readline().strip()
            if first_line == self.READY_SENTINEL:
                print("Pode falar agora.", flush=True)
            stdout_rest, stderr = proc.communicate()
            if proc.returncode != 0:
                detail = (stderr or stdout_rest or first_line).strip()
                raise RuntimeError(
                    "Falha isolada na captura de áudio "
                    f"(processo filho saiu com código {proc.returncode}): "
                    f"{detail or 'sem detalhes'}"
                )

            if diag_path.is_file():
                raw = json.loads(diag_path.read_text(encoding="utf-8"))
                self.last_diagnostics = CaptureDiagnostics(**raw)
            if not wav_path.is_file():
                return PCM16Audio(
                    data=b"", sample_rate=self.config.sample_rate, channels=self.config.channels
                )
            return PCM16Audio.from_wav_bytes(wav_path.read_bytes())


def build_audio_capture(config: AudioConfig) -> AudioCapture:
    backend = config.capture_backend.strip().lower()
    if backend == "pipewire":
        return PipeWireAudioCapture(config)
    if backend == "process":
        return ProcessIsolatedAudioCapture(config)
    if backend == "sounddevice":
        return SoundDeviceAudioCapture(config)
    raise RuntimeError(
        f"Backend de captura inválido: {config.capture_backend!r}. "
        "Use pipewire, process ou sounddevice."
    )
