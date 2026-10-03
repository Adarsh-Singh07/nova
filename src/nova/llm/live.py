"""Gemini Live bidirectional real-time audio and tool execution engine for NOVA.

Uses the official google-genai SDK Live API over WebSockets (gemini-3.8-live)
for low-latency native voice interactions, audio streaming, and asynchronous tool calling.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from nova.core.interfaces import ActionRequest, ActionResult
from nova.llm.credentials import get_gemini_api_key
from nova.llm.tools import get_gemini_function_declarations, parse_tool_call

logger = logging.getLogger(__name__)

GEMINI_LIVE_SYSTEM_INSTRUCTION = (
    "You are NOVA, the fast, private desktop voice assistant. "
    "You speak in a friendly, concise, natural tone. "
    "If the user wants you to do something on their computer (change volume, control media, "
    "launch or close applications, open web pages, search Google, type text into active apps/windows, "
    "press keys like enter/tab/escape, set timers, reminders, or lock/sleep the PC), call the appropriate tool. "
    "Execute tools asynchronously and explain what you did briefly. "
    "When answering general questions or chatting, speak concisely."
)


class GeminiLiveEngine:
    """Manages real-time bidirectional voice sessions with Gemini 3.8 Live."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-3.8-live",
        audio_callback: Callable[[bytes], None] | None = None,
        transcript_callback: Callable[[str, bool], None] | None = None,
        interrupted_callback: Callable[[], None] | None = None,
        action_executor: Callable[[ActionRequest], ActionResult] | None = None,
    ) -> None:
        self.api_key = api_key or get_gemini_api_key()
        self.model = model
        self.audio_callback = audio_callback
        self.transcript_callback = transcript_callback
        self.interrupted_callback = interrupted_callback
        self.action_executor = action_executor
        self._session: Any = None
        self._is_running: bool = False

    def is_available(self) -> bool:
        """Check if Gemini credentials are configured."""
        key = self.api_key or get_gemini_api_key()
        return bool(key and key.strip())

    async def connect_and_stream(self) -> None:
        """Establish WebSocket connection to Gemini Live and begin bidirectional streaming."""
        key = self.api_key or get_gemini_api_key()
        if not key:
            logger.warning("GeminiLiveEngine: Missing Gemini API key.")
            return

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=key)
            tools_decls = get_gemini_function_declarations(non_blocking=True)

            config = types.LiveConnectConfig(
                response_modalities=[types.Modality.AUDIO],
                system_instruction=types.Content(
                    parts=[types.Part(text=GEMINI_LIVE_SYSTEM_INSTRUCTION)]
                ),
                output_audio_transcription=types.AudioTranscriptionConfig(),
                tools=[types.Tool(function_declarations=tools_decls)] if tools_decls else None,
            )

            async with client.aio.live.connect(model=self.model, config=config) as session:
                self._session = session
                self._is_running = True
                logger.info("Connected to Gemini Live session (%s).", self.model)

                async for message in session.receive():
                    if not self._is_running:
                        break

                    # 1. Spoken audio chunks (24kHz PCM)
                    server_content = getattr(message, "server_content", None)
                    if server_content is not None:
                        if getattr(server_content, "interrupted", False):
                            logger.debug("Gemini Live output interrupted by user.")
                            if self.interrupted_callback is not None:
                                self.interrupted_callback()

                        model_turn = getattr(server_content, "model_turn", None)
                        if model_turn is not None:
                            for part in getattr(model_turn, "parts", []):
                                inline = getattr(part, "inline_data", None)
                                if (
                                    inline
                                    and getattr(inline, "data", None)
                                    and self.audio_callback is not None
                                ):
                                    self.audio_callback(inline.data)

                        # User & Assistant Transcripts
                        in_tx = getattr(server_content, "input_transcription", None)
                        if (
                            in_tx
                            and getattr(in_tx, "text", None)
                            and self.transcript_callback is not None
                        ):
                            self.transcript_callback(in_tx.text, True)

                        out_tx = getattr(server_content, "output_transcription", None)
                        if (
                            out_tx
                            and getattr(out_tx, "text", None)
                            and self.transcript_callback is not None
                        ):
                            self.transcript_callback(out_tx.text, False)

                    # 2. Tool Calls
                    tool_call = getattr(message, "tool_call", None)
                    if tool_call is not None:
                        function_calls = getattr(tool_call, "function_calls", [])
                        for call in function_calls:
                            call_id = getattr(call, "id", "")
                            call_name = getattr(call, "name", "")
                            call_args = getattr(call, "args", {})
                            if not isinstance(call_args, dict):
                                call_args = dict(call_args) if call_args is not None else {}

                            logger.info(
                                "Gemini Live tool call received: %s(%s)", call_name, call_args
                            )
                            req = parse_tool_call(call_name, call_args)

                            res_data: dict[str, Any] = {"result": "Action completed successfully."}
                            if req is not None and self.action_executor is not None:
                                try:
                                    res = self.action_executor(req)
                                    res_data = {
                                        "success": res.success,
                                        "result": res.message or "Executed",
                                    }
                                except Exception as exc:
                                    logger.exception("Error executing tool call: %s", exc)
                                    res_data = {"success": False, "error": str(exc)}

                            resp = types.FunctionResponse(
                                id=call_id,
                                name=call_name,
                                response=res_data,
                            )
                            await session.send_tool_response(function_responses=[resp])

        except Exception as e:
            logger.warning("Gemini Live session error: %s", e)
        finally:
            self._session = None
            self._is_running = False

    async def send_audio_chunk(self, pcm_16k_bytes: bytes) -> None:
        """Send raw 16kHz PCM audio chunk to the active Gemini Live session."""
        if self._session is None or not self._is_running:
            return
        try:
            from google.genai import types

            await self._session.send_realtime_input(
                audio=types.Blob(data=pcm_16k_bytes, mime_type="audio/pcm;rate=16000")
            )
        except Exception as e:
            logger.debug("Failed sending audio chunk to Gemini Live: %s", e)

    async def send_text(self, text: str) -> None:
        """Send a text prompt into the active Gemini Live session."""
        if self._session is None or not self._is_running:
            return
        try:
            await self._session.send_realtime_input(text=text)
        except Exception as e:
            logger.debug("Failed sending text to Gemini Live: %s", e)

    def stop(self) -> None:
        """Stop the active live session."""
        self._is_running = False
