"""Security and allowlist validation tests.

Enforces Rule R5 and verifies that arbitrary code execution or shell injection
attempts are strictly blocked.
"""

from __future__ import annotations

import pytest

from nova.core.actions import (
    ActionID,
    ActionValidationError,
    AllowlistValidator,
)
from nova.core.interfaces import ActionRequest


def test_allowlist_membership() -> None:
    assert AllowlistValidator.is_allowlisted(ActionID.VOLUME_UP.value)
    assert AllowlistValidator.is_allowlisted(ActionID.SYSTEM_LOCK.value)
    assert AllowlistValidator.is_allowlisted(ActionID.APP_LAUNCH.value)
    assert not AllowlistValidator.is_allowlisted("system.execute_bash")
    assert not AllowlistValidator.is_allowlisted("shell.exec")
    assert not AllowlistValidator.is_allowlisted("os.system")


def test_destructive_action_identification() -> None:
    assert AllowlistValidator.is_destructive(ActionID.SYSTEM_LOCK.value)
    assert AllowlistValidator.is_destructive(ActionID.SYSTEM_SLEEP.value)
    assert AllowlistValidator.is_destructive(ActionID.APP_CLOSE.value)
    assert not AllowlistValidator.is_destructive(ActionID.VOLUME_UP.value)
    assert not AllowlistValidator.is_destructive(ActionID.APP_LAUNCH.value)
    assert not AllowlistValidator.is_destructive("non_existent_action")


def test_non_allowlisted_action_rejected() -> None:
    req = ActionRequest(action_id="malicious.command", parameters={"cmd": "calc.exe"})
    with pytest.raises(ActionValidationError) as exc_info:
        AllowlistValidator.validate(req)
    assert "not in the allowlist" in str(exc_info.value)


@pytest.mark.parametrize(
    "dangerous_param",
    [
        "spotify; rm -rf /",
        "chrome & notepad",
        "calc | dir",
        "`whoami`",
        "$PATH",
        "app > output.txt",
        "app < input.txt",
        "line1\nline2",
    ],
)
def test_shell_injection_attempt_blocked(dangerous_param: str) -> None:
    req = ActionRequest(
        action_id=ActionID.APP_LAUNCH.value,
        parameters={"app_name": dangerous_param},
    )
    with pytest.raises(ActionValidationError) as exc_info:
        AllowlistValidator.validate(req)
    assert "illegal shell metacharacters" in str(exc_info.value)


def test_volume_set_parameter_validation() -> None:
    # Valid
    valid_req = ActionRequest(action_id=ActionID.VOLUME_SET.value, parameters={"percent": 75})
    AllowlistValidator.validate(valid_req)

    # Missing percent
    with pytest.raises(ActionValidationError) as exc_info:
        AllowlistValidator.validate(
            ActionRequest(action_id=ActionID.VOLUME_SET.value, parameters={})
        )
    assert "requires a 'percent' parameter" in str(exc_info.value)

    # Out of range (>100)
    with pytest.raises(ActionValidationError):
        AllowlistValidator.validate(
            ActionRequest(action_id=ActionID.VOLUME_SET.value, parameters={"percent": 150})
        )

    # Negative percent
    with pytest.raises(ActionValidationError):
        AllowlistValidator.validate(
            ActionRequest(action_id=ActionID.VOLUME_SET.value, parameters={"percent": -10})
        )


def test_app_action_parameter_validation() -> None:
    # Valid app names
    for valid_app in ["Spotify", "Google Chrome", "code-insiders", "vlc_player.exe"]:
        req = ActionRequest(action_id=ActionID.APP_LAUNCH.value, parameters={"app_name": valid_app})
        AllowlistValidator.validate(req)

    # Empty app name
    with pytest.raises(ActionValidationError):
        AllowlistValidator.validate(
            ActionRequest(action_id=ActionID.APP_LAUNCH.value, parameters={"app_name": "  "})
        )

    # Missing app_name
    with pytest.raises(ActionValidationError):
        AllowlistValidator.validate(
            ActionRequest(action_id=ActionID.APP_LAUNCH.value, parameters={})
        )


def test_timer_parameter_validation() -> None:
    # Valid
    AllowlistValidator.validate(
        ActionRequest(action_id=ActionID.TIMER_SET.value, parameters={"duration_seconds": 60})
    )

    # Negative duration
    with pytest.raises(ActionValidationError):
        AllowlistValidator.validate(
            ActionRequest(action_id=ActionID.TIMER_SET.value, parameters={"duration_seconds": -5})
        )

    # Missing parameter
    with pytest.raises(ActionValidationError):
        AllowlistValidator.validate(
            ActionRequest(action_id=ActionID.TIMER_SET.value, parameters={})
        )


def test_note_and_search_validation() -> None:
    # Valid note
    AllowlistValidator.validate(
        ActionRequest(action_id=ActionID.NOTE_APPEND.value, parameters={"text": "Buy milk"})
    )
    # Empty note
    with pytest.raises(ActionValidationError):
        AllowlistValidator.validate(
            ActionRequest(action_id=ActionID.NOTE_APPEND.value, parameters={"text": "  "})
        )

    # Valid search
    AllowlistValidator.validate(
        ActionRequest(
            action_id=ActionID.WEB_SEARCH.value, parameters={"query": "python 3.11 release date"}
        )
    )
    # Empty search
    with pytest.raises(ActionValidationError):
        AllowlistValidator.validate(
            ActionRequest(action_id=ActionID.WEB_SEARCH.value, parameters={"query": ""})
        )
