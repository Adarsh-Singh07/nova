"""Allowlisted actions and strict parameter validation for NOVA.

Enforces Rule R5: NOVA will never execute arbitrary shell commands or unconstrained
code. All executable actions must map to a finite, strongly-typed allowlist with
sanitized parameters.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any

from nova.core.interfaces import ActionRequest


class ActionID(StrEnum):
    """Finite allowlist of supported system and application actions."""

    # Volume Controls
    VOLUME_SET = "volume.set"
    VOLUME_UP = "volume.up"
    VOLUME_DOWN = "volume.down"
    VOLUME_MUTE_TOGGLE = "volume.mute_toggle"

    # Media Controls
    MEDIA_PLAY_PAUSE = "media.play_pause"
    MEDIA_NEXT = "media.next"
    MEDIA_PREVIOUS = "media.previous"

    # System State Controls (Destructive/Disruptive)
    SYSTEM_LOCK = "system.lock"
    SYSTEM_SLEEP = "system.sleep"

    # Application Controls
    APP_LAUNCH = "app.launch"
    APP_CLOSE = "app.close"

    # Interface & System Appearance
    DARK_MODE_TOGGLE = "system.dark_mode_toggle"

    # Productivity & Utilities
    TIMER_SET = "productivity.timer_set"
    NOTE_APPEND = "productivity.note_append"
    WEB_SEARCH = "web.search"
    CONVERSATION_REPLY = "conversation.reply"


# Actions classified as destructive/disruptive requiring user confirmation by default
DESTRUCTIVE_ACTIONS: set[ActionID] = {
    ActionID.SYSTEM_LOCK,
    ActionID.SYSTEM_SLEEP,
    ActionID.APP_CLOSE,
}

# Strict regex disallowing shell metacharacters in text arguments (prevent injection)
DANGEROUS_SHELL_CHARACTERS_REGEX = re.compile(r"[`$&|;><\n\r\t]")


class ActionValidationError(ValueError):
    """Raised when an action request violates security constraints or schema."""


class AllowlistValidator:
    """Security validator ensuring every ActionRequest is strictly bounded and safe."""

    @classmethod
    def is_allowlisted(cls, action_id: str) -> bool:
        """Check if an action identifier exists in the strict allowlist."""
        return any(action_id == item.value for item in ActionID)

    @classmethod
    def is_destructive(cls, action_id: str) -> bool:
        """Check if an action is classified as destructive."""
        try:
            return ActionID(action_id) in DESTRUCTIVE_ACTIONS
        except ValueError:
            return False

    @classmethod
    def validate(cls, request: ActionRequest) -> None:
        """Validate an ActionRequest against typing, ranges, and injection rules.

        Raises:
            ActionValidationError: If the action is not allowlisted or parameters are unsafe.
        """
        if not cls.is_allowlisted(request.action_id):
            raise ActionValidationError(
                f"Action '{request.action_id}' is not in the allowlist. Arbitrary execution rejected."
            )

        action_enum = ActionID(request.action_id)
        params = request.parameters

        # Check for dangerous shell characters across all string parameters
        for key, value in params.items():
            if isinstance(value, str) and DANGEROUS_SHELL_CHARACTERS_REGEX.search(value):
                raise ActionValidationError(
                    f"Parameter '{key}' contains illegal shell metacharacters: '{value}'"
                )

        # Action-specific parameter contract validation
        if action_enum == ActionID.VOLUME_SET:
            cls._validate_volume_set(params)
        elif action_enum in (ActionID.APP_LAUNCH, ActionID.APP_CLOSE):
            cls._validate_app_name(params)
        elif action_enum == ActionID.TIMER_SET:
            cls._validate_timer(params)
        elif action_enum == ActionID.NOTE_APPEND:
            cls._validate_note(params)
        elif action_enum == ActionID.WEB_SEARCH:
            cls._validate_search(params)

    @staticmethod
    def _validate_volume_set(params: dict[str, Any]) -> None:
        if "percent" not in params:
            raise ActionValidationError("volume.set requires a 'percent' parameter.")
        percent = params["percent"]
        if not isinstance(percent, int) or not (0 <= percent <= 100):
            raise ActionValidationError(
                f"Volume percent must be an integer between 0 and 100, got: {percent}"
            )

    @staticmethod
    def _validate_app_name(params: dict[str, Any]) -> None:
        if "app_name" not in params or not isinstance(params["app_name"], str):
            raise ActionValidationError(
                "Application actions require a string 'app_name' parameter."
            )
        app_name = params["app_name"].strip()
        if not app_name:
            raise ActionValidationError("Application name cannot be empty.")
        # Allow alphanumeric, spaces, hyphens, underscores, dots
        if not re.match(r"^[\w\s\.\-]+$", app_name):
            raise ActionValidationError(f"Invalid characters in application name: '{app_name}'")

    @staticmethod
    def _validate_timer(params: dict[str, Any]) -> None:
        if "duration_seconds" not in params:
            raise ActionValidationError("timer_set requires 'duration_seconds' parameter.")
        duration = params["duration_seconds"]
        if not isinstance(duration, (int, float)) or duration <= 0:
            raise ActionValidationError(f"Timer duration must be positive, got: {duration}")

    @staticmethod
    def _validate_note(params: dict[str, Any]) -> None:
        if "text" not in params or not isinstance(params["text"], str):
            raise ActionValidationError("note_append requires a string 'text' parameter.")
        if not params["text"].strip():
            raise ActionValidationError("Note text cannot be empty.")

    @staticmethod
    def _validate_search(params: dict[str, Any]) -> None:
        if "query" not in params or not isinstance(params["query"], str):
            raise ActionValidationError("web.search requires a string 'query' parameter.")
        if not params["query"].strip():
            raise ActionValidationError("Search query cannot be empty.")
