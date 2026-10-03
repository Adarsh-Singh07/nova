"""Unit tests for credentials and pipeline keyboard actions."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from nova.core.actions import ActionID
from nova.core.fakes import (
    FakeConfirmationHandler,
    FakeIntentEngine,
    FakePlatformAdapter,
    FakeSTTEngine,
    FakeTTSEngine,
)
from nova.core.interfaces import ActionRequest
from nova.core.pipeline import NovaPipeline
from nova.core.settings import NovaSettings
from nova.core.state import PipelineStateMachine
from nova.llm.credentials import (
    get_agnes_api_key,
    get_agnes_base_url,
    get_agnes_model,
    get_gemini_api_key,
    set_agnes_api_key,
    set_gemini_api_key,
)


def test_credentials_functions(monkeypatch: pytest.MonkeyPatch) -> None:
    # Test Agnes base url & model
    assert get_agnes_base_url() == "https://apihub.agnes-ai.com/v1"
    assert get_agnes_model() == "agnes-3.0-flash"

    # Test setting and reading Gemini key
    set_gemini_api_key("unit-test-gemini-key")
    assert get_gemini_api_key() == "unit-test-gemini-key"

    # Test setting and reading Agnes key
    set_agnes_api_key("unit-test-agnes-key")
    assert get_agnes_api_key() == "unit-test-agnes-key"

    # Test fallback to keyring when env var is cleared
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with patch("keyring.get_password", return_value="keyring-gemini-val"):
        assert get_gemini_api_key() == "keyring-gemini-val"

    monkeypatch.delenv("AGNES_API_KEY", raising=False)
    with patch("keyring.get_password", return_value="keyring-agnes-val"):
        assert get_agnes_api_key() == "keyring-agnes-val"


def test_pipeline_keyboard_actions_execution() -> None:
    platform = FakePlatformAdapter()
    pipeline = NovaPipeline(
        state_machine=PipelineStateMachine(),
        stt=FakeSTTEngine(),
        intent_engine=FakeIntentEngine(),
        tts=FakeTTSEngine(),
        platform=platform,
        settings=NovaSettings(),
        confirmation_handler=FakeConfirmationHandler(auto_confirm=True),
    )

    from nova.core.state import PipelineState

    # 1. Test keyboard typing
    type_req = ActionRequest(
        action_id=ActionID.KEYBOARD_TYPE.value,
        parameters={"text": "Hello world from pipeline test"},
        feedback_phrase="Typing text.",
        raw_query="type hello world",
    )
    pipeline.state_machine.transition_to(PipelineState.THINKING)
    res = pipeline._process_action_request(type_req, "type hello world")
    assert res.success is True
    assert "Hello world from pipeline test" in platform.typed_texts

    # 2. Test keyboard key press
    press_req = ActionRequest(
        action_id=ActionID.KEYBOARD_PRESS.value,
        parameters={"key": "enter"},
        feedback_phrase="Pressing enter.",
        raw_query="press enter",
    )
    pipeline.state_machine.transition_to(PipelineState.THINKING)
    res_press = pipeline._process_action_request(press_req, "press enter")
    assert res_press.success is True
    assert "enter" in platform.pressed_keys
