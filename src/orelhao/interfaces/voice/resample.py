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

    target_count = max(1, int(round(samples.size * target_sample_rate / audio.sample_rate)))
    source_positions = np.arange(samples.size, dtype=np.float64)
    target_positions = np.linspace(0, samples.size - 1, target_count, dtype=np.float64)
    resampled = np.interp(target_positions, source_positions, samples.astype(np.float64))
    resampled = np.clip(np.rint(resampled), -32768, 32767).astype(np.int16)

    return PCM16Audio(
        data=resampled.tobytes(),
        sample_rate=target_sample_rate,
        channels=1,
    )
