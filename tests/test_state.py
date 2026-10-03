"""Unit tests for the pipeline finite state machine."""

from __future__ import annotations

import pytest

from nova.core.state import (
    InvalidStateTransitionError,
    PipelineState,
    PipelineStateMachine,
)


def test_initial_state() -> None:
    sm = PipelineStateMachine()
    assert sm.current_state == PipelineState.IDLE


def test_valid_sequential_transitions() -> None:
    sm = PipelineStateMachine()

    transitions = [
        PipelineState.LISTENING,
        PipelineState.TRANSCRIBING,
        PipelineState.THINKING,
        PipelineState.ACTING,
        PipelineState.SPEAKING,
        PipelineState.IDLE,
    ]

    for target in transitions:
        assert sm.can_transition_to(target)
        sm.transition_to(target)
        assert sm.current_state == target


def test_invalid_transition_raises() -> None:
    sm = PipelineStateMachine()
    assert not sm.can_transition_to(PipelineState.ACTING)

    with pytest.raises(InvalidStateTransitionError) as exc_info:
        sm.transition_to(PipelineState.ACTING)

    assert exc_info.value.from_state == PipelineState.IDLE
    assert exc_info.value.to_state == PipelineState.ACTING


def test_idempotent_transition() -> None:
    sm = PipelineStateMachine(PipelineState.IDLE)
    # Transitioning to the current state is a no-op
    sm.transition_to(PipelineState.IDLE)
    assert sm.current_state == PipelineState.IDLE


def test_listeners_notified() -> None:
    sm = PipelineStateMachine()
    events: list[tuple[PipelineState, PipelineState]] = []

    def callback(old: PipelineState, new: PipelineState) -> None:
        events.append((old, new))

    sm.add_listener(callback)
    sm.transition_to(PipelineState.LISTENING)
    sm.transition_to(PipelineState.TRANSCRIBING)

    assert events == [
        (PipelineState.IDLE, PipelineState.LISTENING),
        (PipelineState.LISTENING, PipelineState.TRANSCRIBING),
    ]

    sm.remove_listener(callback)
    sm.transition_to(PipelineState.IDLE)
    # Should not receive the last transition
    assert len(events) == 2


def test_listener_exception_handled() -> None:
    sm = PipelineStateMachine()

    def faulty_listener(old: PipelineState, new: PipelineState) -> None:
        raise RuntimeError("Listener exploded")

    sm.add_listener(faulty_listener)
    # Should not raise or prevent state transition
    sm.transition_to(PipelineState.LISTENING)
    assert sm.current_state == PipelineState.LISTENING


def test_reset() -> None:
    sm = PipelineStateMachine()
    sm.transition_to(PipelineState.LISTENING)
    assert sm.can_transition_to(PipelineState.TRANSCRIBING)

    sm.reset()
    assert sm.current_state == PipelineState.IDLE

    # Resetting while already idle does not emit duplicate reset events
    sm.reset()
    assert sm.current_state == PipelineState.IDLE
