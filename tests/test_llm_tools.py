"""Unit tests for allowlisted LLM tools and schema conversions."""

from __future__ import annotations

from nova.core.actions import ActionID
from nova.llm.tools import (
    get_gemini_function_declarations,
    get_openai_tools,
    parse_tool_call,
)


def test_tool_schemas_defined() -> None:
    tools = get_openai_tools()
    assert len(tools) >= 15
    names = [t["function"]["name"] for t in tools]
    assert "volume_set" in names
    assert "app_launch" in names
    assert "keyboard_type" in names
    assert "keyboard_press" in names
    assert "conversation_reply" in names


def test_gemini_declarations() -> None:
    decls = get_gemini_function_declarations(non_blocking=True)
    assert len(decls) >= 15


def test_parse_tool_call_volume() -> None:
    req = parse_tool_call("volume_set", {"percent": 75}, raw_query="set volume to 75")
    assert req is not None
    assert req.action_id == ActionID.VOLUME_SET.value
    assert req.parameters["percent"] == 75

    req_up = parse_tool_call("volume_change", {"direction": "up"})
    assert req_up is not None
    assert req_up.action_id == ActionID.VOLUME_UP.value

    req_mute = parse_tool_call("volume_mute_toggle", {})
    assert req_mute is not None
    assert req_mute.action_id == ActionID.VOLUME_MUTE_TOGGLE.value


def test_parse_tool_call_media() -> None:
    for act, expected_id in [
        ("play_pause", ActionID.MEDIA_PLAY_PAUSE.value),
        ("next", ActionID.MEDIA_NEXT.value),
        ("previous", ActionID.MEDIA_PREVIOUS.value),
        ("stop", ActionID.MEDIA_STOP.value),
    ]:
        req = parse_tool_call("media_control", {"action": act})
        assert req is not None
        assert req.action_id == expected_id


def test_parse_tool_call_apps() -> None:
    req_launch = parse_tool_call("app_launch", {"app_name": "Brave Browser"})
    assert req_launch is not None
    assert req_launch.action_id == ActionID.APP_LAUNCH.value
    assert req_launch.parameters["app_name"] == "Brave Browser"

    req_close = parse_tool_call("app_close", {"app_name": "Spotify"})
    assert req_close is not None
    assert req_close.action_id == ActionID.APP_CLOSE.value
    assert req_close.is_destructive is True


def test_parse_tool_call_system() -> None:
    req_lock = parse_tool_call("system_lock", {})
    assert req_lock is not None
    assert req_lock.action_id == ActionID.SYSTEM_LOCK.value
    assert req_lock.is_destructive is True

    req_sleep = parse_tool_call("system_sleep", {})
    assert req_sleep is not None
    assert req_sleep.action_id == ActionID.SYSTEM_SLEEP.value

    req_theme = parse_tool_call("dark_mode_toggle", {})
    assert req_theme is not None
    assert req_theme.action_id == ActionID.DARK_MODE_TOGGLE.value


def test_parse_tool_call_web() -> None:
    req_search = parse_tool_call("web_search", {"query": "Pitsport bookmarks"})
    assert req_search is not None
    assert req_search.action_id == ActionID.WEB_SEARCH.value
    assert req_search.parameters["query"] == "Pitsport bookmarks"

    req_url = parse_tool_call("web_open_url", {"url": "https://pitsport.com"})
    assert req_url is not None
    assert req_url.action_id == ActionID.WEB_OPEN_URL.value
    assert req_url.parameters["url"] == "https://pitsport.com"


def test_parse_tool_call_productivity() -> None:
    req_timer = parse_tool_call("timer_set", {"duration_seconds": 120})
    assert req_timer is not None
    assert req_timer.action_id == ActionID.TIMER_SET.value
    assert req_timer.parameters["duration_seconds"] == 120.0

    req_remind = parse_tool_call("reminder_set", {"text": "check oven", "seconds": 300})
    assert req_remind is not None
    assert req_remind.action_id == ActionID.REMINDER_SET.value

    req_note = parse_tool_call("note_append", {"text": "remember eggs"})
    assert req_note is not None
    assert req_note.action_id == ActionID.NOTE_APPEND.value


def test_parse_tool_call_keyboard() -> None:
    req_type = parse_tool_call("keyboard_type", {"text": "Hello world!"})
    assert req_type is not None
    assert req_type.action_id == ActionID.KEYBOARD_TYPE.value
    assert req_type.parameters["text"] == "Hello world!"

    req_press = parse_tool_call("keyboard_press", {"key": "enter"})
    assert req_press is not None
    assert req_press.action_id == ActionID.KEYBOARD_PRESS.value
    assert req_press.parameters["key"] == "enter"

    # Disallowed key fails validation
    req_bad_key = parse_tool_call("keyboard_press", {"key": "bad_key_123"})
    assert req_bad_key is None


def test_parse_tool_call_conversation_and_malicious() -> None:
    req_reply = parse_tool_call("conversation_reply", {"reply": "Today is sunny!"})
    assert req_reply is not None
    assert req_reply.action_id == ActionID.CONVERSATION_REPLY.value
    assert req_reply.parameters["reply"] == "Today is sunny!"

    # Unrecognized tool returns None
    assert parse_tool_call("unknown_tool", {}) is None

    # Shell injection in app name fails allowlist validation
    req_inject = parse_tool_call("app_launch", {"app_name": "calc; rm -rf /"})
    assert req_inject is None
