"""Turn-based Gemini LLM provider for NOVA.

Uses the official google-genai SDK for single-turn intent resolution and conversational
reasoning with allowlisted function calls.
"""

from __future__ import annotations

import logging
from typing import Any

from nova.core.actions import ActionID, AllowlistValidator
from nova.core.interfaces import ActionRequest
from nova.llm.credentials import get_gemini_api_key
from nova.llm.tools import get_gemini_function_declarations, parse_tool_call

logger = logging.getLogger(__name__)

GEMINI_SYSTEM_INSTRUCTION = (
    "You are NOVA, a private, ultra-responsive desktop voice assistant. "
    "If the user wants to perform an action (e.g. adjust volume, control media, launch/close applications, "
    "type text into an app or form field, press keys like enter/tab, open websites, search the web, "
    "set timers or reminders, lock or sleep the PC), call the appropriate tool. "
    "If the user is having a conversation or asking a question, provide a helpful and concise spoken response."
)


class GeminiTurnProvider:
    """Turn-based client using Google GenAI SDK for Gemini models."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-2.0-flash",
        timeout_seconds: float = 10.0,
    ) -> None:
        self.api_key = api_key or get_gemini_api_key()
        self.model = model
        self.timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        """Check if Gemini API key is configured."""
        key = self.api_key or get_gemini_api_key()
        return bool(key and key.strip())

    def _get_client(self) -> Any:
        key = self.api_key or get_gemini_api_key()
        if not key:
            return None
        from google import genai

        return genai.Client(api_key=key)

    async def resolve_intent_async(self, text: str) -> ActionRequest | None:
        """Asynchronously resolve query into an ActionRequest using Gemini."""
        client = self._get_client()
        if client is None:
            logger.debug("GeminiTurnProvider: No API key found.")
            return None

        try:
            from google.genai import types

            func_decls = get_gemini_function_declarations()
            config = types.GenerateContentConfig(
                system_instruction=GEMINI_SYSTEM_INSTRUCTION,
                tools=[types.Tool(function_declarations=func_decls)] if func_decls else None,
                temperature=0.2,
            )

            response = await client.aio.models.generate_content(
                model=self.model,
                contents=text,
                config=config,
            )

            return self._parse_gemini_response(response, text)
        except Exception as e:
            logger.warning("GeminiTurnProvider async call failed: %s", e)
            return None

    def resolve_intent(self, text: str) -> ActionRequest | None:
        """Synchronously resolve query into an ActionRequest using Gemini."""
        client = self._get_client()
        if client is None:
            logger.debug("GeminiTurnProvider: No API key found.")
            return None

        try:
            from google.genai import types

            func_decls = get_gemini_function_declarations()
            config = types.GenerateContentConfig(
                system_instruction=GEMINI_SYSTEM_INSTRUCTION,
                tools=[types.Tool(function_declarations=func_decls)] if func_decls else None,
                temperature=0.2,
            )

            response = client.models.generate_content(
                model=self.model,
                contents=text,
                config=config,
            )

            return self._parse_gemini_response(response, text)
        except Exception as e:
            logger.warning("GeminiTurnProvider call failed: %s", e)
            return None

    def _parse_gemini_response(self, response: Any, raw_query: str) -> ActionRequest | None:
        """Extract tool call or text content from Gemini response."""
        try:
            # 1. Check for function calls
            if hasattr(response, "function_calls") and response.function_calls:
                call = response.function_calls[0]
                name = getattr(call, "name", "")
                args = getattr(call, "args", {})
                if not isinstance(args, dict):
                    args = dict(args) if args is not None else {}
                parsed = parse_tool_call(name, args, raw_query=raw_query)
                if parsed is not None:
                    return parsed

            # 2. Check for text response
            text = getattr(response, "text", None)
            if text and isinstance(text, str) and text.strip():
                reply = text.strip()
                req = ActionRequest(
                    action_id=ActionID.CONVERSATION_REPLY.value,
                    parameters={"reply": reply},
                    feedback_phrase=reply,
                    raw_query=raw_query,
                )
                AllowlistValidator.validate(req)
                return req

            return None
        except Exception as e:
            logger.warning("Error parsing Gemini response: %s", e)
            return None
