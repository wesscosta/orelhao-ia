from __future__ import annotations

import numpy as np

from orelhao.interfaces.voice.audio import PCM16Audio


def resample_pcm16(audio: PCM16Audio, target_sample_rate: int) -> PCM16Audio:
    """Resample PCM16 audio using linear interpolation.

    This utility is intentionally dependency-light and suitable for speech audio.
    The internal voice pipeline remains at 16 kHz even when the physical device
    requires 44.1/48 kHz.
    """
    if target_sample_rate <= 0:
        raise ValueError("target_sample_rate deve ser positivo")
    if audio.sample_rate == target_sample_rate or not audio.data:
        return PCM16Audio(
            data=audio.data,
            sample_rate=target_sample_rate,
            channels=audio.channels,
        )
    if audio.channels != 1:
        raise ValueError("Resampling nesta etapa suporta apenas áudio mono")

    samples = np.frombuffer(audio.data, dtype=np.int16)
    if samples.size == 0:
        return PCM16Audio(data=b"", sample_rate=target_sample_rate, channels=1)

    target_count = max(1, round(samples.size * target_sample_rate / audio.sample_rate))
    source_positions = np.arange(samples.size, dtype=np.float64)
    target_positions = np.linspace(0, samples.size - 1, target_count, dtype=np.float64)
    resampled = np.interp(target_positions, source_positions, samples.astype(np.float64))
    resampled = np.clip(np.rint(resampled), -32768, 32767).astype(np.int16)

    return PCM16Audio(
        data=resampled.tobytes(),
        sample_rate=target_sample_rate,
        channels=1,
    )


def trim_silence_pcm16(
    audio: PCM16Audio,
    *,
    frame_ms: int = 20,
    padding_ms: int = 200,
) -> PCM16Audio:
    """Remove silêncio nas bordas de uma gravação curta feita no navegador."""
    if audio.channels != 1:
        raise ValueError("Remoção de silêncio suporta apenas áudio mono")
    if not audio.data:
        return audio
    samples = np.frombuffer(audio.data, dtype=np.int16)
    frame_size = max(1, audio.sample_rate * frame_ms // 1000)
    frame_count = samples.size // frame_size
    if frame_count == 0:
        return audio
    framed = samples[: frame_count * frame_size].reshape(frame_count, frame_size)
    rms = np.sqrt(np.mean(framed.astype(np.float64) ** 2, axis=1))
    noise_floor = float(np.percentile(rms, 20))
    threshold = min(2_000.0, max(250.0, noise_floor * 2.5))
    voiced = np.flatnonzero(rms >= threshold)
    if voiced.size == 0:
        return PCM16Audio(data=b"", sample_rate=audio.sample_rate, channels=1)
    padding_frames = max(0, padding_ms // frame_ms)
    first = max(0, int(voiced[0]) - padding_frames)
    last = min(frame_count, int(voiced[-1]) + padding_frames + 1)
    trimmed = samples[first * frame_size : last * frame_size]
    return PCM16Audio(data=trimmed.tobytes(), sample_rate=audio.sample_rate, channels=1)
