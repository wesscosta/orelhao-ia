import pytest

from orelhao.core.conversation.state_machine import (
    ConversationStateMachine,
    InvalidTransition,
    State,
)


def test_initial_state_is_on_hook() -> None:
    machine = ConversationStateMachine()
    assert machine.state == State.ON_HOOK


def test_valid_session_transition() -> None:
    machine = ConversationStateMachine()
    machine.transition(State.OFF_HOOK)
    machine.transition(State.LISTENING)
    assert machine.state == State.LISTENING


def test_invalid_transition_is_rejected() -> None:
    machine = ConversationStateMachine()
    with pytest.raises(InvalidTransition):
        machine.transition(State.GENERATING)
