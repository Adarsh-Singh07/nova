"""Unit tests for GeminiLiveEngine (bidirectional WebSockets & tool calling)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nova.core.actions import ActionID
from nova.core.interfaces import ActionRequest, ActionResult
from nova.llm.live import GeminiLiveEngine


def test_live_engine_is_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with patch("nova.llm.live.get_gemini_api_key", return_value=None):
        e_no = GeminiLiveEngine(api_key="")
        assert e_no.is_available() is False

    e_yes = GeminiLiveEngine(api_key="valid-key")
    assert e_yes.is_available() is True


def test_live_engine_send_when_disconnected() -> None:
    import asyncio

    async def _run() -> None:
        engine = GeminiLiveEngine(api_key="valid-key")
        # Must not raise error when not connected
        await engine.send_audio_chunk(b"\x00\x01" * 100)
        await engine.send_text("hello")

    asyncio.run(_run())


def test_live_engine_streaming_events() -> None:
    import asyncio

    async def _run() -> None:
        audio_chunks: list[bytes] = []
        transcripts: list[tuple[str, bool]] = []
        interrupted_calls: list[bool] = []
        executed_actions: list[ActionRequest] = []

        def mock_audio_cb(data: bytes) -> None:
            audio_chunks.append(data)

        def mock_tx_cb(text: str, is_user: bool) -> None:
            transcripts.append((text, is_user))

        def mock_int_cb() -> None:
            interrupted_calls.append(True)

        def mock_action_exec(req: ActionRequest) -> ActionResult:
            executed_actions.append(req)
            return ActionResult(success=True, message=f"Executed {req.action_id}")

        engine = GeminiLiveEngine(
            api_key="test-key",
            audio_callback=mock_audio_cb,
            transcript_callback=mock_tx_cb,
            interrupted_callback=mock_int_cb,
            action_executor=mock_action_exec,
        )

        # 1. Message with audio part
        msg_audio = MagicMock()
        part = MagicMock()
        part.inline_data = MagicMock(data=b"RAW_PCM_24K_AUDIO")
        turn = MagicMock(parts=[part])
        msg_audio.server_content = MagicMock(
            model_turn=turn,
            interrupted=False,
            input_transcription=None,
            output_transcription=None,
        )
        msg_audio.tool_call = None

        # 2. Message with transcripts
        msg_tx = MagicMock()
        in_tx = MagicMock(text="turn volume down")
        out_tx = MagicMock(text="Decreasing volume.")
        msg_tx.server_content = MagicMock(
            model_turn=None,
            interrupted=False,
            input_transcription=in_tx,
            output_transcription=out_tx,
        )
        msg_tx.tool_call = None

        # 3. Message with interruption
        msg_int = MagicMock()
        msg_int.server_content = MagicMock(
            model_turn=None,
            interrupted=True,
            input_transcription=None,
            output_transcription=None,
        )
        msg_int.tool_call = None

        # 4. Message with tool call
        msg_tool = MagicMock()
        msg_tool.server_content = None
        call = MagicMock()
        call.id = "call_xyz"
        call.name = "volume_change"
        call.args = {"direction": "down"}
        msg_tool.tool_call = MagicMock(function_calls=[call])

        # Async generator simulating session.receive()
        async def mock_receive():
            yield msg_audio
            yield msg_tx
            yield msg_int
            yield msg_tool

        mock_session = MagicMock()
        mock_session.receive = mock_receive
        mock_session.send_tool_response = AsyncMock()

        class MockContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        mock_client = MagicMock()
        mock_client.aio.live.connect.return_value = MockContextManager()

        with patch("google.genai.Client", return_value=mock_client):
            await engine.connect_and_stream()

        # Verify audio chunks
        assert b"RAW_PCM_24K_AUDIO" in audio_chunks

        # Verify transcripts
        assert ("turn volume down", True) in transcripts
        assert ("Decreasing volume.", False) in transcripts

        # Verify interruption
        assert len(interrupted_calls) == 1

        # Verify tool execution and response
        assert len(executed_actions) == 1
        assert executed_actions[0].action_id == ActionID.VOLUME_DOWN.value
        mock_session.send_tool_response.assert_called_once()

    asyncio.run(_run())
