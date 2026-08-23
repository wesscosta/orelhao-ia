import pytest

from orelhao.interfaces.voice.devices import resolve_device


class FakeSD:
    def query_devices(self):
        return [
            {"name": "HDMI 0", "max_input_channels": 0, "max_output_channels": 8},
            {"name": "USB Microphone", "max_input_channels": 1, "max_output_channels": 0},
            {"name": "Built-in Audio Analog Stereo", "max_input_channels": 2, "max_output_channels": 2},
        ]


def test_resolve_by_name_and_capability():
    sd = FakeSD()
    assert resolve_device(sd, "USB Microphone", "input") == 1
    assert resolve_device(sd, "Built-in Audio", "output") == 2


def test_reject_hdmi_as_input():
    sd = FakeSD()
    with pytest.raises(ValueError, match="não possui canais de input"):
        resolve_device(sd, 0, "input")
