from enum import StrEnum, auto


class State(StrEnum):
    ON_HOOK = auto()
    OFF_HOOK = auto()
    LISTENING = auto()
    TRANSCRIBING = auto()
    RETRIEVING = auto()
    GENERATING = auto()
    SPEAKING = auto()
    ERROR = auto()
    RECOVERY = auto()


_ALLOWED: dict[State, set[State]] = {
    State.ON_HOOK: {State.OFF_HOOK},
    State.OFF_HOOK: {State.LISTENING, State.ON_HOOK, State.ERROR},
    State.LISTENING: {State.TRANSCRIBING, State.ON_HOOK, State.ERROR},
    State.TRANSCRIBING: {State.RETRIEVING, State.ON_HOOK, State.ERROR},
    State.RETRIEVING: {State.GENERATING, State.ON_HOOK, State.ERROR},
    State.GENERATING: {State.SPEAKING, State.ON_HOOK, State.ERROR},
    State.SPEAKING: {State.LISTENING, State.ON_HOOK, State.ERROR},
    State.ERROR: {State.RECOVERY, State.ON_HOOK},
    State.RECOVERY: {State.ON_HOOK},
}


class InvalidTransition(RuntimeError):
    pass


class ConversationStateMachine:
    def __init__(self) -> None:
        self.state = State.ON_HOOK

    def transition(self, new_state: State) -> None:
        if new_state not in _ALLOWED[self.state]:
            raise InvalidTransition(f"Transição inválida: {self.state} -> {new_state}")
        self.state = new_state
