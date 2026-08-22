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
