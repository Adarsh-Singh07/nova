"""Unit tests for AgnesProvider (Agnes 3.0 Flash)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from nova.core.actions import ActionID
from nova.llm.agnes import AgnesProvider


def test_agnes_is_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGNES_API_KEY", raising=False)
    with patch("nova.llm.agnes.get_agnes_api_key", return_value=None):
        p_no_key = AgnesProvider(api_key="")
        assert p_no_key.is_available() is False

    p_with_key = AgnesProvider(api_key="test-key")
    assert p_with_key.is_available() is True


def test_agnes_resolve_tool_call() -> None:
    provider = AgnesProvider(api_key="fake-key")

    mock_resp_data = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_123",
                            "type": "function",
                            "function": {
                                "name": "app_launch",
                                "arguments": json.dumps({"app_name": "Brave"}),
                            },
                        }
                    ],
                }
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_resp_data

    with patch("httpx.Client.post", return_value=mock_resp):
        res = provider.resolve_intent("open brave browser")
        assert res is not None
        assert res.action_id == ActionID.APP_LAUNCH.value
        assert res.parameters["app_name"] == "Brave"


def test_agnes_resolve_conversational_reply() -> None:
    provider = AgnesProvider(api_key="fake-key")

    mock_resp_data = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "The weather today in Paris is sunny with 22 degrees.",
                    "tool_calls": [],
                }
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_resp_data

    with patch("httpx.Client.post", return_value=mock_resp):
        res = provider.resolve_intent("what's the weather in Paris?")
        assert res is not None
        assert res.action_id == ActionID.CONVERSATION_REPLY.value
        assert "Paris" in res.parameters["reply"]


def test_agnes_resolve_async() -> None:
    import asyncio

    async def _run() -> None:
        provider = AgnesProvider(api_key="fake-key")

        mock_resp_data = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_456",
                                "type": "function",
                                "function": {
                                    "name": "keyboard_type",
                                    "arguments": json.dumps({"text": "Hello Agnes!"}),
                                },
                            }
                        ],
                    }
                }
            ]
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_resp_data

        with patch("httpx.AsyncClient.post", return_value=mock_resp):
            res = await provider.resolve_intent_async("type hello agnes")
            assert res is not None
            assert res.action_id == ActionID.KEYBOARD_TYPE.value
            assert res.parameters["text"] == "Hello Agnes!"

    asyncio.run(_run())


def test_agnes_network_error_fallback() -> None:
    provider = AgnesProvider(api_key="fake-key")

    with patch("httpx.Client.post", side_effect=Exception("Connection timed out")):
        res = provider.resolve_intent("any command")
        assert res is None
