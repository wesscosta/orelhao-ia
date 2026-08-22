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
