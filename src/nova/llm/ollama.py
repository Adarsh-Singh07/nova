"""Local Ollama LLM provider for 100% offline fallback in NOVA.

Enforces Rule R5.1 (Offline-first by default): Runs locally on localhost:11434
with zero network access and zero telemetry.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from nova.core.actions import ActionID, AllowlistValidator
from nova.core.interfaces import ActionRequest
from nova.llm.tools import get_openai_tools, parse_tool_call

logger = logging.getLogger(__name__)

OLLAMA_SYSTEM_PROMPT = (
    "You are NOVA, an offline desktop voice assistant. "
    "If the user wants to perform a system action (volume, media, open apps, close apps, "
    "lock, sleep, search, open url, type text, press keys, timers, reminders), choose the appropriate tool. "
    "Otherwise, reply with a short conversational message."
)


class OllamaProvider:
    """Local offline LLM provider using Ollama HTTP API."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3:8b",
        timeout_seconds: float = 6.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        """Check if local Ollama daemon is reachable."""
        try:
            with httpx.Client(timeout=1.0) as client:
                resp = client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    async def resolve_intent_async(self, text: str) -> ActionRequest | None:
        """Asynchronously resolve query via Ollama."""
        url = f"{self.base_url}/api/chat"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": OLLAMA_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "tools": get_openai_tools(),
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code != 200:
                    return None
                data = resp.json()
                return self._parse_response(data, text)
        except Exception as e:
            logger.debug("Ollama async request failed: %s", e)
            return None

    def resolve_intent(self, text: str) -> ActionRequest | None:
        """Synchronously resolve query via Ollama."""
        url = f"{self.base_url}/api/chat"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": OLLAMA_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "tools": get_openai_tools(),
            "stream": False,
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(url, json=payload)
                if resp.status_code != 200:
                    return None
                data = resp.json()
                return self._parse_response(data, text)
        except Exception as e:
            logger.debug("Ollama request failed: %s", e)
            return None

    def _parse_response(self, data: dict[str, Any], raw_query: str) -> ActionRequest | None:
        """Parse Ollama response into ActionRequest."""
        try:
            message = data.get("message", {})

            # 1. Tool calls
            tool_calls = message.get("tool_calls", [])
            if tool_calls:
                call = tool_calls[0]
                fn = call.get("function", {})
                name = fn.get("name", "")
                args = fn.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                parsed = parse_tool_call(name, args, raw_query=raw_query)
                if parsed is not None:
                    return parsed

            # 2. Conversational text
            content = message.get("content")
            if content and isinstance(content, str) and content.strip():
                reply = content.strip()
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
            logger.warning("Error parsing Ollama response: %s", e)
            return None
