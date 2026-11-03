"""Contrato e seguranca do protocolo de gancho ESP32."""
from orelhao.hardware.hook import HookSensor
from orelhao.hardware.serial_hook import HookSerialAdapter, parse_hook_event

VALID = (
    '{"protocol":"orelhao.hook.v1","kind":"change","gpio":27,'
    '"contact":"open","seq":2,"uptime_ms":1500}'
)


def test_valid_open_event() -> None:
    event = parse_hook_event(VALID)
    assert event is not None
    assert (event.contact, event.gpio, event.seq) == ("open", 27, 2)


def test_rejects_invalid_and_untrusted_serial_lines() -> None:
    for payload in (
        b"\xff\xff", "bootnoise", "", "{}", "[]" , "x" * 257,
        VALID.replace('"gpio":27', '"gpio":26'),
        VALID.replace('"protocol":"orelhao.hook.v1"', '"protocol":"other"'),
        VALID.replace('"seq":2', '"seq":true'),
        VALID.replace('"uptime_ms":1500', '"uptime_ms":-1'),
    ):
        assert parse_hook_event(payload) is None


def test_observation_does_not_arm_conversation() -> None:
    sensor = HookSensor()
    adapter = HookSerialAdapter(sensor)
    adapter.accept(VALID)
    assert adapter.last_contact == "open"
    assert not sensor.is_off_hook()


def test_calibrated_hook_transitions_and_fail_safe_disconnect() -> None:
    sensor = HookSensor()
    adapter = HookSerialAdapter(sensor, off_hook_contact="open")
    adapter.accept(VALID)
    assert sensor.is_off_hook()
    adapter.accept(VALID.replace('"contact":"open"', '"contact":"closed"'))
    assert not sensor.is_off_hook()
    adapter.accept(VALID)
    assert sensor.is_off_hook()
    adapter.disconnected()
    assert not sensor.is_off_hook()
    assert adapter.last_contact is None
