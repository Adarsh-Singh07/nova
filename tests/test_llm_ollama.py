"""Unit tests for OllamaProvider (offline local fallback)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from nova.core.actions import ActionID
from nova.llm.ollama import OllamaProvider


def test_ollama_is_available() -> None:
    provider = OllamaProvider()

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("httpx.Client.get", return_value=mock_resp):
        assert provider.is_available() is True

    with patch("httpx.Client.get", side_effect=Exception("Connection refused")):
        assert provider.is_available() is False


def test_ollama_resolve_tool_call() -> None:
    provider = OllamaProvider()

    mock_data = {
        "message": {
            "role": "assistant",
            "tool_calls": [
                {
                    "function": {
                        "name": "dark_mode_toggle",
                        "arguments": {},
                    }
                }
            ],
        }
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_data

    with patch("httpx.Client.post", return_value=mock_resp):
        res = provider.resolve_intent("switch to dark theme")
        assert res is not None
        assert res.action_id == ActionID.DARK_MODE_TOGGLE.value


def test_ollama_resolve_text() -> None:
    provider = OllamaProvider()

    mock_data = {
        "message": {
            "role": "assistant",
            "content": "Hello! I am your local offline assistant.",
        }
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_data

    with patch("httpx.Client.post", return_value=mock_resp):
        res = provider.resolve_intent("hello there")
        assert res is not None
        assert res.action_id == ActionID.CONVERSATION_REPLY.value
        assert "offline assistant" in res.parameters["reply"]


def test_ollama_unreachable() -> None:
    provider = OllamaProvider()

    with patch("httpx.Client.post", side_effect=Exception("Connection refused")):
        res = provider.resolve_intent("any prompt")
        assert res is None


def test_ollama_async_and_errors() -> None:
    import asyncio

    async def _run() -> None:
        provider = OllamaProvider()

        # 1. Non-200 status code
        mock_500 = MagicMock(status_code=500)
        with patch("httpx.AsyncClient.post", return_value=mock_500):
            assert await provider.resolve_intent_async("test") is None

        # 2. Async success with stringified JSON arguments
        mock_data = {
            "message": {
                "tool_calls": [
                    {
                        "function": {
                            "name": "volume_set",
                            "arguments": '{"percent": 80}',
                        }
                    }
                ]
            }
        }
        mock_200 = MagicMock(status_code=200)
        mock_200.json.return_value = mock_data
        with patch("httpx.AsyncClient.post", return_value=mock_200):
            res = await provider.resolve_intent_async("set volume to 80")
            assert res is not None
            assert res.action_id == ActionID.VOLUME_SET.value
            assert res.parameters["percent"] == 80

        # 3. Exception in async
        with patch("httpx.AsyncClient.post", side_effect=Exception("Timeout")):
            assert await provider.resolve_intent_async("test") is None

    asyncio.run(_run())
