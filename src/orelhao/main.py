from __future__ import annotations

import argparse
import os

from orelhao.config import load_config
from orelhao.core.conversation.session import Session
from orelhao.core.conversation.state_machine import ConversationStateMachine, State
from orelhao.infrastructure.telemetry.metrics import Metrics
from orelhao.interfaces.voice.capture import MockAudioCapture, SoundDeviceAudioCapture
from orelhao.interfaces.voice.playback import MockAudioPlayback, SoundDeviceAudioPlayback
from orelhao.services.llm.service import MockLLMService
from orelhao.services.rag.retriever import MockRetriever
from orelhao.services.stt.service import MockSTTService
from orelhao.services.tts.service import MockTTSService


def _config():
    path = os.getenv("ORELHAO_CONFIG", "config/development.yaml")
    return load_config(path)


def run_mock_pipeline() -> None:
    config = _config()
    machine = ConversationStateMachine()
    session = Session()
    metrics = Metrics(sessions_started=1)

    capture = MockAudioCapture(config.audio.sample_rate)
    playback = MockAudioPlayback()
    stt = MockSTTService()
    retriever = MockRetriever()
    llm = MockLLMService()
    tts = MockTTSService()

    print(f"{config.name} [{config.environment}] — sessão {session.id}")
    machine.transition(State.OFF_HOOK)
    machine.transition(State.LISTENING)
    audio = capture.capture()

    machine.transition(State.TRANSCRIBING)
    query = stt.transcribe(audio)
    print(f"Usuário: {query}")

    machine.transition(State.RETRIEVING)
    context = retriever.search(query)
    machine.transition(State.GENERATING)
    answer = llm.generate(query, context)
    print(f"Assistente: {answer}")

    machine.transition(State.SPEAKING)
    playback.play(tts.synthesize(answer))
    session.register_turn()
    metrics.turns_completed += 1
    machine.transition(State.ON_HOOK)
    print(f"Sessão finalizada. Estado={machine.state}; turnos={session.turns}")


def audio_loopback() -> None:
    config = _config()
    capture = SoundDeviceAudioCapture(config.audio)
    playback = SoundDeviceAudioPlayback(config.audio)
    print("Fale após esta mensagem. A captura termina após o silêncio configurado...")
    audio = capture.capture()
    if not audio.data:
        print("Nenhuma fala detectada.")
        return
    print(f"Capturado: {audio.duration_seconds:.2f}s. Reproduzindo...")
    playback.play(audio)


def list_audio_devices() -> None:
    try:
        import sounddevice as sd
    except ImportError as exc:
        raise SystemExit("Instale o suporte de áudio: pip install -e '.[audio]'") from exc
    print(sd.query_devices())


def main() -> None:
    parser = argparse.ArgumentParser(description="Orelhão IA")
    parser.add_argument("--audio-loopback", action="store_true", help="testa captura + VAD + playback")
    parser.add_argument("--list-audio-devices", action="store_true", help="lista interfaces de áudio")
    args = parser.parse_args()

    if args.list_audio_devices:
        list_audio_devices()
    elif args.audio_loopback:
        audio_loopback()
    else:
        run_mock_pipeline()


if __name__ == "__main__":
    main()
