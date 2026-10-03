"""Finite state machine for the NOVA pipeline.

Defines all pipeline states, transition constraints, and thread-safe transition notifications.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from enum import StrEnum

logger = logging.getLogger(__name__)


class PipelineState(StrEnum):
    """Enumeration of all valid pipeline states."""

    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    ACTING = "acting"
    SPEAKING = "speaking"
    ERROR = "error"


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal state transition is attempted."""

    def __init__(self, from_state: PipelineState, to_state: PipelineState) -> None:
        super().__init__(
            f"Invalid pipeline state transition from {from_state.value} to {to_state.value}"
        )
        self.from_state = from_state
        self.to_state = to_state


# Set of permitted transitions: current_state -> set(valid_next_states)
VALID_TRANSITIONS: dict[PipelineState, set[PipelineState]] = {
    PipelineState.IDLE: {
        PipelineState.LISTENING,
        PipelineState.TRANSCRIBING,  # Headless text input can jump directly to transcribing/thinking
        PipelineState.THINKING,
        PipelineState.ERROR,
    },
    PipelineState.LISTENING: {
        PipelineState.TRANSCRIBING,
        PipelineState.IDLE,  # Cancelled or silence timeout
        PipelineState.ERROR,
    },
    PipelineState.TRANSCRIBING: {
        PipelineState.THINKING,
        PipelineState.IDLE,  # No speech detected or discarded
        PipelineState.ERROR,
    },
    PipelineState.THINKING: {
        PipelineState.AWAITING_CONFIRMATION,
        PipelineState.ACTING,
        PipelineState.SPEAKING,  # Conversational reply without action
        PipelineState.IDLE,
        PipelineState.ERROR,
    },
    PipelineState.AWAITING_CONFIRMATION: {
        PipelineState.ACTING,  # Confirmed
        PipelineState.SPEAKING,  # Cancelled with spoken feedback
        PipelineState.IDLE,  # Dismissed silently
        PipelineState.ERROR,
    },
    PipelineState.ACTING: {
        PipelineState.SPEAKING,  # Action completed with voice feedback
        PipelineState.IDLE,  # Action completed silently
        PipelineState.ERROR,
    },
    PipelineState.SPEAKING: {
        PipelineState.IDLE,  # Finished speaking
        PipelineState.LISTENING,  # User barged in with push-to-talk
        PipelineState.ERROR,
    },
    PipelineState.ERROR: {
        PipelineState.SPEAKING,  # Speaking error feedback
        PipelineState.IDLE,  # Error acknowledged / reset
    },
}

StateListener = Callable[[PipelineState, PipelineState], None]


class PipelineStateMachine:
    """Thread-safe finite state machine enforcing strict transition rules."""

    def __init__(self, initial_state: PipelineState = PipelineState.IDLE) -> None:
        self._current_state = initial_state
        self._lock = threading.RLock()
        self._listeners: list[StateListener] = []

    @property
    def current_state(self) -> PipelineState:
        """Return the current pipeline state."""
        with self._lock:
            return self._current_state

    def add_listener(self, listener: StateListener) -> None:
        """Register a callback for state changes: callback(old_state, new_state)."""
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def remove_listener(self, listener: StateListener) -> None:
        """Unregister a state change callback."""
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def can_transition_to(self, target_state: PipelineState) -> bool:
        """Check if transition from current state to target state is legally permitted."""
        with self._lock:
            return target_state in VALID_TRANSITIONS.get(self._current_state, set())

    def transition_to(self, target_state: PipelineState) -> None:
        """Transition to target state or raise InvalidStateTransitionError."""
        with self._lock:
            if target_state == self._current_state:
                return

            if not self.can_transition_to(target_state):
                logger.error(
                    "Illegal transition rejected: %s -> %s",
                    self._current_state.value,
                    target_state.value,
                )
                raise InvalidStateTransitionError(self._current_state, target_state)

            old_state = self._current_state
            self._current_state = target_state
            logger.debug(
                "Pipeline state transitioned: %s -> %s",
                old_state.value,
                target_state.value,
            )
            listeners = list(self._listeners)

        for listener in listeners:
            try:
                listener(old_state, target_state)
            except Exception:
                logger.exception("Exception in pipeline state listener callback")

    def reset(self) -> None:
        """Force reset the state machine back to IDLE state."""
        with self._lock:
            old_state = self._current_state
            self._current_state = PipelineState.IDLE
            listeners = list(self._listeners)

        if old_state != PipelineState.IDLE:
            logger.info("Pipeline state reset to IDLE from %s", old_state.value)
            for listener in listeners:
                try:
                    listener(old_state, PipelineState.IDLE)
                except Exception:
                    logger.exception("Exception in state listener during reset")
