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
    VOLUME_APP_SET = "volume.app_set"

    # Media Controls
    MEDIA_PLAY_PAUSE = "media.play_pause"
    MEDIA_NEXT = "media.next"
    MEDIA_PREVIOUS = "media.previous"
    MEDIA_STOP = "media.stop"

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
    STOPWATCH_START = "productivity.stopwatch_start"
    STOPWATCH_STOP = "productivity.stopwatch_stop"
    STOPWATCH_RESET = "productivity.stopwatch_reset"
    STOPWATCH_STATUS = "productivity.stopwatch_status"
    REMINDER_SET = "productivity.reminder_set"
    NOTE_APPEND = "productivity.note_append"
    WEB_SEARCH = "web.search"
    WEB_OPEN_URL = "web.open_url"
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
        elif action_enum == ActionID.VOLUME_APP_SET:
            cls._validate_volume_app_set(params)
        elif action_enum in (ActionID.APP_LAUNCH, ActionID.APP_CLOSE):
            cls._validate_app_name(params)
        elif action_enum == ActionID.TIMER_SET:
            cls._validate_timer(params)
        elif action_enum == ActionID.REMINDER_SET:
            cls._validate_reminder(params)
        elif action_enum == ActionID.NOTE_APPEND:
            cls._validate_note(params)
        elif action_enum == ActionID.WEB_SEARCH:
            cls._validate_search(params)
        elif action_enum == ActionID.WEB_OPEN_URL:
            cls._validate_open_url(params)

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
    def _validate_volume_app_set(params: dict[str, Any]) -> None:
        if "app_name" not in params or not isinstance(params["app_name"], str):
            raise ActionValidationError("volume.app_set requires a string 'app_name' parameter.")
        app_name = params["app_name"].strip()
        if not app_name or not re.match(r"^[\w\s\.\-]+$", app_name):
            raise ActionValidationError(f"Invalid application name: '{app_name}'")

        if "percent" in params and params["percent"] is not None:
            percent = params["percent"]
            if not isinstance(percent, int) or not (0 <= percent <= 100):
                raise ActionValidationError(f"Percent must be 0-100, got: {percent}")

        if "direction" in params and params["direction"] is not None:
            direction = params["direction"]
            if direction not in ("up", "down", "mute", "set"):
                raise ActionValidationError(f"Invalid direction: '{direction}'")

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
    def _validate_reminder(params: dict[str, Any]) -> None:
        if "text" not in params or not isinstance(params["text"], str):
            raise ActionValidationError("reminder_set requires a string 'text' parameter.")
        if not params["text"].strip():
            raise ActionValidationError("Reminder text cannot be empty.")
        if "seconds" in params and params["seconds"] is not None:
            seconds = params["seconds"]
            if not isinstance(seconds, (int, float)) or seconds <= 0:
                raise ActionValidationError(f"Reminder seconds must be positive, got: {seconds}")

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

    @staticmethod
    def _validate_open_url(params: dict[str, Any]) -> None:
        if "url" not in params or not isinstance(params["url"], str):
            raise ActionValidationError("web.open_url requires a string 'url' parameter.")
        url = params["url"].strip()
        if not url.startswith(("http://", "https://")):
            raise ActionValidationError(f"URL must start with http:// or https://, got: '{url}'")
