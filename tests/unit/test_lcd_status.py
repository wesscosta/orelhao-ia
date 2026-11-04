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


def test_answer_pagination_and_lifecycle() -> None:
    data = {"session_id": "s", "active": True, "events": [
        {"type": "voice.response", "turn": 1, "timestamp": "t1",
         "text": "A inscrição está aberta para cursos de informática e tecnologia."},
    ]}
    port = FakeSerial()
    lcd = LCDStatusBridge(interval=0.1, show_answers=True, page_seconds=1.0)
    lcd.tick(port, session_id="s", snapshot_fn=lambda: data, now=1.0)
    assert port.commands[0].startswith(b"LCD:TEXT:LUMI:")
    lcd.tick(port, session_id="s", snapshot_fn=lambda: data, now=1.2)
    assert len(port.commands) == 1
    lcd.tick(port, session_id="s", snapshot_fn=lambda: data, now=2.2)
    assert len(port.commands) == 2
    lcd.tick(port, session_id=None, snapshot_fn=lambda: data, now=3.5)
    assert port.commands[-1] == b"LCD:STATE:READY\n"
    assert lcd._token is None and not lcd._pages


def test_response_through_playback_then_next_listening() -> None:
    data = {"session_id": "s", "active": True, "events": [
        {"type": "voice.response", "turn": 1, "text": "Bem-vindo ao Senac."},
        {"type": "voice.playback", "turn": 1, "status": "concluida"},
    ]}
    port = FakeSerial()
    lcd = LCDStatusBridge(interval=0.1, show_answers=True)
    lcd.tick(port, session_id="s", snapshot_fn=lambda: data, now=1.0)
    assert port.commands[-1].startswith(b"LCD:TEXT:")
    data["events"].append({"type": "voice.listening", "turn": 2})
    lcd.tick(port, session_id="s", snapshot_fn=lambda: data, now=2.0)
    assert port.commands[-1] == b"LCD:STATE:LISTENING\n"


def test_previous_session_answer_is_not_sent() -> None:
    data = {"session_id": "old", "active": True, "events": [
        {"type": "voice.response", "text": "segredo"},
    ]}
    port = FakeSerial()
    lcd = LCDStatusBridge(show_answers=True)
    lcd.tick(port, session_id="new", snapshot_fn=lambda: data, now=1.0)
    assert port.commands == [b"LCD:STATE:PROCESSING\n"]
    assert b"segredo" not in b"".join(port.commands)


def test_lcd_protocol_sanitizes_controls_and_accents() -> None:
    from orelhao.hardware.lcd_status import display_pages

    pages = display_pages("Olá|Mundo\nLCD:STATE:ERROR  São   José")
    assert pages
    text = "".join("".join(page) for page in pages)
    assert "Ola/Mundo" in text
    assert "Sao" in text and "Jose" in text
    assert all(len(row) <= 16 for page in pages for row in page)
    assert all(all(32 <= ord(c) <= 126 for c in row) for page in pages for row in page)


def test_lcd_answer_is_bounded_with_ellipsis() -> None:
    from orelhao.hardware.lcd_status import display_pages

    pages = display_pages("mensagem " * 300)
    assert pages
    assert "..." in "".join("".join(page) for page in pages)
    assert sum(len(line) for page in pages for line in page) <= 490


def test_invalid_transcription_not_exposed() -> None:
    data = {"session_id": "s", "active": True, "events": [
        {"type": "voice.transcription_invalid", "text": "CPF 123.456.789-00"},
    ]}
    port = FakeSerial()
    lcd = LCDStatusBridge(show_answers=True)
    lcd.tick(port, session_id="s", snapshot_fn=lambda: data, now=1.0)
    assert port.commands == [b"LCD:STATE:LISTENING\n"]
