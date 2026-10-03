"""Unit tests for GeminiTurnProvider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nova.core.actions import ActionID
from nova.llm.gemini_turn import GeminiTurnProvider


def test_gemini_turn_is_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with patch("nova.llm.gemini_turn.get_gemini_api_key", return_value=None):
        p_no = GeminiTurnProvider(api_key="")
        assert p_no.is_available() is False

    p_yes = GeminiTurnProvider(api_key="gemini-key-xyz")
    assert p_yes.is_available() is True


def test_gemini_turn_function_call() -> None:
    provider = GeminiTurnProvider(api_key="gemini-key-xyz")

    # Mock response with function call
    mock_call = MagicMock()
    mock_call.name = "web_search"
    mock_call.args = {"query": "Pitsport bookmark"}

    mock_resp = MagicMock()
    mock_resp.function_calls = [mock_call]
    mock_resp.text = None

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_resp

    with patch.object(provider, "_get_client", return_value=mock_client):
        res = provider.resolve_intent("search for pitsport bookmark")
        assert res is not None
        assert res.action_id == ActionID.WEB_SEARCH.value
        assert res.parameters["query"] == "Pitsport bookmark"


def test_gemini_turn_text_reply() -> None:
    provider = GeminiTurnProvider(api_key="gemini-key-xyz")

    mock_resp = MagicMock()
    mock_resp.function_calls = []
    mock_resp.text = "The speed of light is roughly 300,000 kilometers per second."

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_resp

    with patch.object(provider, "_get_client", return_value=mock_client):
        res = provider.resolve_intent("how fast is light?")
        assert res is not None
        assert res.action_id == ActionID.CONVERSATION_REPLY.value
        assert "speed of light" in res.parameters["reply"]


def test_gemini_turn_async() -> None:
    import asyncio

    async def _run() -> None:
        provider = GeminiTurnProvider(api_key="gemini-key-xyz")

        mock_call = MagicMock()
        mock_call.name = "keyboard_press"
        mock_call.args = {"key": "enter"}

        mock_resp = MagicMock()
        mock_resp.function_calls = [mock_call]
        mock_resp.text = None

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)

        with patch.object(provider, "_get_client", return_value=mock_client):
            res = await provider.resolve_intent_async("press enter key")
            assert res is not None
            assert res.action_id == ActionID.KEYBOARD_PRESS.value
            assert res.parameters["key"] == "enter"

    asyncio.run(_run())


def test_gemini_turn_error_fallback() -> None:
    provider = GeminiTurnProvider(api_key="gemini-key-xyz")

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("API quota exceeded")

    with patch.object(provider, "_get_client", return_value=mock_client):
        res = provider.resolve_intent("search for tests")
        assert res is None
