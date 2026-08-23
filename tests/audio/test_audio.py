from array import array

from orelhao.interfaces.voice.audio import PCM16Audio
from orelhao.interfaces.voice.vad import EnergyVAD


def test_pcm16_wav_roundtrip() -> None:
    audio = PCM16Audio(data=b"\x00\x00" * 1600, sample_rate=16_000, channels=1)
    recovered = PCM16Audio.from_wav_bytes(audio.to_wav_bytes())
    assert recovered.data == audio.data
    assert recovered.sample_rate == 16_000
    assert recovered.channels == 1


def test_energy_vad_detects_silence_and_signal() -> None:
    vad = EnergyVAD(rms_threshold=0.01)
    silence = b"\x00\x00" * 480
    signal = array("h", [12_000] * 480).tobytes()
    assert not vad.is_speech(silence)
    assert vad.is_speech(signal)


def test_resample_pcm16_preserves_duration_approximately() -> None:
    from orelhao.interfaces.voice.resample import resample_pcm16

    # 100 ms at 44.1 kHz -> ~100 ms at 16 kHz.
    source = PCM16Audio(data=b"\x00\x00" * 4410, sample_rate=44_100, channels=1)
    target = resample_pcm16(source, 16_000)
    assert target.sample_rate == 16_000
    assert target.channels == 1
    assert abs(target.duration_seconds - source.duration_seconds) < 0.002
    assert len(target.data) == 1600 * 2


def test_resample_pcm16_noop_when_rate_matches() -> None:
    from orelhao.interfaces.voice.resample import resample_pcm16

    source = PCM16Audio(data=b"\x01\x00" * 160, sample_rate=16_000, channels=1)
    target = resample_pcm16(source, 16_000)
    assert target.data == source.data
    assert target.sample_rate == 16_000


def test_adaptive_vad_calibrates_from_noise_floor() -> None:
    from orelhao.interfaces.voice.vad import AdaptiveEnergyVAD

    noise = array("h", [100] * 480).tobytes()
    voice = array("h", [10_000] * 480).tobytes()
    vad = AdaptiveEnergyVAD(threshold_multiplier=3.0, min_threshold=0.001, max_threshold=0.08)
    threshold = vad.calibrate([noise] * 8)
    assert 0.001 <= threshold <= 0.08
    assert not vad.is_speech(noise)
    assert vad.is_speech(voice)


def test_adaptive_vad_respects_threshold_limits() -> None:
    from orelhao.interfaces.voice.vad import AdaptiveEnergyVAD

    silence = b"\x00\x00" * 480
    vad = AdaptiveEnergyVAD(threshold_multiplier=100.0, min_threshold=0.006, max_threshold=0.08)
    assert vad.calibrate([silence]) == 0.006


def test_adaptive_vad_uses_quiet_half_for_calibration() -> None:
    from orelhao.interfaces.voice.vad import AdaptiveEnergyVAD

    quiet = array("h", [100] * 480).tobytes()
    loud = array("h", [20_000] * 480).tobytes()
    vad = AdaptiveEnergyVAD(threshold_multiplier=3.0, min_threshold=0.001, max_threshold=0.08)
    threshold = vad.calibrate([quiet] * 5 + [loud] * 5)
    assert threshold < 0.02
    assert vad.is_speech(loud)


def test_speech_gate_requires_sustained_start() -> None:
    from orelhao.interfaces.voice.vad import SpeechGate, SpeechGateState

    gate = SpeechGate(3, 5, 4, 2)
    assert gate.observe(True) is None
    assert gate.observe(False) is None
    assert gate.state is SpeechGateState.WAITING
    assert gate.observe(True) is None
    assert gate.observe(True) is None
    assert gate.observe(True) == "speech_started"
    assert gate.state is SpeechGateState.SPEAKING


def test_speech_gate_tolerates_short_pause_and_ends_after_long_silence() -> None:
    from orelhao.interfaces.voice.vad import SpeechGate, SpeechGateState

    gate = SpeechGate(2, 4, 3, 2)
    gate.observe(True)
    assert gate.observe(True) == "speech_started"
    gate.observe(True)
    gate.observe(True)
    assert gate.observe(False) is None
    assert gate.observe(True) is None
    assert gate.observe(False) is None
    assert gate.observe(False) is None
    assert gate.observe(False) == "speech_ended"
    assert gate.state is SpeechGateState.COMPLETE


def test_speech_gate_rejects_false_start() -> None:
    from orelhao.interfaces.voice.vad import SpeechGate, SpeechGateState

    gate = SpeechGate(2, 5, 4, 2)
    gate.observe(True)
    assert gate.observe(True) == "speech_started"
    assert gate.observe(False) is None
    assert gate.observe(False) == "false_start"
    assert gate.state is SpeechGateState.WAITING


def test_capture_diagnostics_exposes_peak_rms():
    from orelhao.interfaces.voice.capture import CaptureDiagnostics

    diag = CaptureDiagnostics(
        hardware_rate=16000,
        pipeline_rate=16000,
        noise_floor=0.01,
        speech_threshold=0.018,
        speech_detected=False,
        stop_reason="speech_start_timeout",
        peak_rms=0.04,
    )
    assert diag.peak_rms == 0.04


def test_adaptive_vad_default_is_more_sensitive():
    from orelhao.interfaces.voice.vad import AdaptiveEnergyVAD

    vad = AdaptiveEnergyVAD()
    assert vad.threshold_multiplier == 1.8
    assert vad.max_threshold == 0.05


def test_webrtc_vad_rejects_invalid_aggressiveness():
    import pytest
    from orelhao.interfaces.voice.vad import WebRTCVAD
    with pytest.raises(ValueError):
        WebRTCVAD(4)


def test_webrtc_vad_silence():
    import pytest
    pytest.importorskip("webrtcvad")
    from orelhao.interfaces.voice.vad import WebRTCVAD
    vad = WebRTCVAD(2)
    assert vad.is_speech(b"\x00\x00" * 480, 16000) is False


def test_hysteresis_gate_starts_and_ends_with_windows():
    from orelhao.interfaces.voice.vad import HysteresisSpeechGate, SpeechGateState

    gate = HysteresisSpeechGate(
        start_window_blocks=10,
        start_ratio=0.5,
        min_voiced_blocks=5,
        end_window_blocks=20,
        end_ratio=0.1,
    )
    events = [
        gate.observe(v)
        for v in [True, False, True, True, False, True, True, False, True, False]
    ]
    assert "speech_started" in events
    assert gate.state is SpeechGateState.SPEAKING

    event = None
    for i in range(20):
        event = gate.observe(i == 0)
    assert event == "speech_ended"
    assert gate.state is SpeechGateState.COMPLETE


def test_vad_end_window_allows_natural_pauses():
    from orelhao.config import AudioConfig
    cfg = AudioConfig()
    assert cfg.vad_end_window_ms == 1500
