"""LLM and Tier 2 reasoning interfaces and providers for NOVA."""

from __future__ import annotations

from nova.llm.agnes import AgnesProvider
from nova.llm.cascade import CascadeIntentEngine
from nova.llm.credentials import (
    get_agnes_api_key,
    get_agnes_base_url,
    get_agnes_model,
    get_gemini_api_key,
    set_agnes_api_key,
    set_gemini_api_key,
)
from nova.llm.gemini_turn import GeminiTurnProvider
from nova.llm.live import GeminiLiveEngine
from nova.llm.ollama import OllamaProvider
from nova.llm.tools import NOVA_TOOLS_SCHEMA, get_openai_tools, parse_tool_call

__all__ = [
    "NOVA_TOOLS_SCHEMA",
    "AgnesProvider",
    "CascadeIntentEngine",
    "GeminiLiveEngine",
    "GeminiTurnProvider",
    "OllamaProvider",
    "get_agnes_api_key",
    "get_agnes_base_url",
    "get_agnes_model",
    "get_gemini_api_key",
    "get_openai_tools",
    "parse_tool_call",
    "set_agnes_api_key",
    "set_gemini_api_key",
]
