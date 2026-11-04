"""LCD events are optional and must not compromise the hook protocol."""
from __future__ import annotations

from orelhao.hardware.lcd_status import LCDStatusBridge, choose_state


class FakeSerial:
    def __init__(self) -> None:
        self.commands: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.commands.append(data)


def test_no_session_ready_and_no_user_text_leaks() -> None:
    data = {"session_id": "sess1", "active": True, "events": [
        {"type": "voice.transcription", "text": "Meu CPF e 123"},
        {"type": "voice.response", "text": "informacao reservada"},
    ]}
    assert choose_state(data, None) == "READY"
    assert choose_state(data, "sess1") == "SPEAKING"
    port = FakeSerial()
    reporter = LCDStatusBridge()
    reporter.tick(port, session_id="sess1", snapshot_fn=lambda: data, now=1.0)
    assert port.commands == [b"LCD:STATE:SPEAKING\n"]
    assert b"CPF" not in b"".join(port.commands)


def test_old_session_is_ignored() -> None:
    data = {"session_id": "old", "active": True, "events": [
        {"type": "voice.listening"}]}
    assert choose_state(data, "new") == "PROCESSING"


def test_transitions_and_deduplication() -> None:
    data = {"session_id": "s", "active": True, "events": [
        {"type": "voice.greeting"}]}
    port = FakeSerial()
    reporter = LCDStatusBridge(interval=0.5)
    reporter.tick(port, session_id=None, snapshot_fn=lambda: data, now=1.0)
    reporter.tick(port, session_id="s", snapshot_fn=lambda: data, now=1.6)
    reporter.tick(port, session_id="s", snapshot_fn=lambda: data, now=2.2)
    data["events"].append({"type": "voice.listening"})
    reporter.tick(port, session_id="s", snapshot_fn=lambda: data, now=2.8)
    reporter.tick(port, session_id=None, snapshot_fn=lambda: data, now=3.4)
    assert port.commands == [
        b"LCD:STATE:READY\n", b"LCD:STATE:SPEAKING\n",
        b"LCD:STATE:LISTENING\n", b"LCD:STATE:READY\n",
    ]


def test_waiting_for_knowledge_is_processing_not_user_pause() -> None:
    data = {"session_id": "s", "active": True, "events": [{"type": "voice.waiting"}]}
    assert choose_state(data, "s") == "PROCESSING"
    data["events"].append({"type": "voice.paused"})
    assert choose_state(data, "s") == "PAUSED"


def test_invalid_state_not_sent() -> None:
    port = FakeSerial()
    reporter = LCDStatusBridge()
    reporter.send(port, "FAKE\nLCD:STATE:ERROR")
    assert port.commands == []
