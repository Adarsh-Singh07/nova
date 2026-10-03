"""Agnes 3.0 Flash LLM client for NOVA.

Provides high-throughput, low-latency intent resolution and conversational responses
via an OpenAI-compatible endpoint with unlimited tokens.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from nova.core.actions import ActionID, AllowlistValidator
from nova.core.interfaces import ActionRequest
from nova.llm.credentials import get_agnes_api_key, get_agnes_base_url, get_agnes_model
from nova.llm.tools import get_openai_tools, parse_tool_call

logger = logging.getLogger(__name__)

AGNES_SYSTEM_PROMPT = (
    "You are NOVA, a private, ultra-responsive desktop voice assistant. "
    "Your job is to assist the user by controlling the system or answering questions. "
    "If the user wants to control the system (volume, media playback, launch/close applications, "
    "open websites, search the web, type text into the active window, press keys like enter/tab, "
    "set timers or reminders, lock or sleep the PC), call the appropriate tool. "
    "If the user is asking a conversational question or chatting, provide a concise, natural, spoken reply."
)


class AgnesProvider:
    """Turn-based client for Agnes 3.0 Flash."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 8.0,
    ) -> None:
        self.api_key = api_key or get_agnes_api_key()
        self.base_url = (base_url or get_agnes_base_url()).rstrip("/")
        self.model = model or get_agnes_model()
        self.timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        """Check if Agnes API credentials are configured."""
        key = self.api_key or get_agnes_api_key()
        return bool(key and key.strip())

    async def resolve_intent_async(self, text: str) -> ActionRequest | None:
        """Asynchronously resolve user query into an allowlisted ActionRequest."""
        key = self.api_key or get_agnes_api_key()
        if not key:
            logger.debug("AgnesProvider: No API key found.")
            return None

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": AGNES_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "tools": get_openai_tools(),
            "tool_choice": "auto",
            "temperature": 0.2,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()

            return self._parse_response(data, text)
        except httpx.HTTPStatusError as e:
            logger.warning("Agnes HTTP error %s: %s", e.response.status_code, e.response.text)
            return None
        except Exception as e:
            logger.warning("Agnes request failed: %s", e)
            return None

    def resolve_intent(self, text: str) -> ActionRequest | None:
        """Synchronously resolve user query into an allowlisted ActionRequest."""
        key = self.api_key or get_agnes_api_key()
        if not key:
            logger.debug("AgnesProvider: No API key found.")
            return None

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": AGNES_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "tools": get_openai_tools(),
            "tool_choice": "auto",
            "temperature": 0.2,
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()

            return self._parse_response(data, text)
        except httpx.HTTPStatusError as e:
            logger.warning("Agnes HTTP error %s: %s", e.response.status_code, e.response.text)
            return None
        except Exception as e:
            logger.warning("Agnes request failed: %s", e)
            return None

    def _parse_response(self, data: dict[str, Any], raw_query: str) -> ActionRequest | None:
        """Parse chat completion response into ActionRequest."""
        try:
            choices = data.get("choices", [])
            if not choices:
                return None

            message = choices[0].get("message", {})

            # 1. Tool Call handling
            tool_calls = message.get("tool_calls", [])
            if tool_calls:
                call = tool_calls[0]
                fn = call.get("function", {})
                name = fn.get("name", "")
                raw_args = fn.get("arguments", "{}")
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except Exception:
                    args = {}

                parsed = parse_tool_call(name, args, raw_query=raw_query)
                if parsed is not None:
                    return parsed

            # 2. Conversational text response fallback
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
            logger.warning("Error parsing Agnes response: %s", e)
            return None
