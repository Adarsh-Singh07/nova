"""Tier 2 LLM Cascade Intent Engine for NOVA.

Cascades across:
  1. Tier 1 Local Regex (0ms, offline)
  2. Agnes 3.0 Flash (Primary high-throughput text & tool engine, unlimited tokens)
  3. Gemini 2.0 Flash (Secondary cloud fallback)
  4. Local Ollama (Tertiary 100% offline fallback)
"""

from __future__ import annotations

import logging

from nova.core.interfaces import ActionRequest, IntentEngineProtocol
from nova.core.settings import LLMSettings
from nova.intent.tier1 import Tier1IntentEngine
from nova.llm.agnes import AgnesProvider
from nova.llm.gemini_turn import GeminiTurnProvider
from nova.llm.ollama import OllamaProvider

logger = logging.getLogger(__name__)


class CascadeIntentEngine(IntentEngineProtocol):
    """Hybrid intent resolver cascading from Tier 1 regex to multi-model Tier 2 LLMs."""

    def __init__(
        self,
        settings: LLMSettings | None = None,
        tier1_engine: Tier1IntentEngine | None = None,
        agnes_provider: AgnesProvider | None = None,
        gemini_provider: GeminiTurnProvider | None = None,
        ollama_provider: OllamaProvider | None = None,
    ) -> None:
        self.settings = settings or LLMSettings()
        self.tier1 = tier1_engine or Tier1IntentEngine()
        self.agnes = agnes_provider or AgnesProvider(
            base_url=self.settings.agnes_base_url,
            model=self.settings.agnes_model,
            timeout_seconds=self.settings.timeout_seconds,
        )
        self.gemini = gemini_provider or GeminiTurnProvider(
            model=self.settings.gemini_model,
            timeout_seconds=self.settings.timeout_seconds,
        )
        self.ollama = ollama_provider or OllamaProvider(
            base_url=self.settings.ollama_base_url,
            model=self.settings.ollama_model,
            timeout_seconds=self.settings.timeout_seconds,
        )

    def resolve_intent(self, text: str) -> ActionRequest | None:
        """Resolve user intent synchronously cascading through available tiers."""
        # 1. Tier 1: Local regex & fuzzy matching (0ms latency, zero cloud)
        t1_result = self.tier1.resolve_intent(text)
        if t1_result is not None:
            logger.debug("Resolved intent via Tier 1 local engine: %s", t1_result.action_id)
            return t1_result

        # If LLM processing is disabled or offline, return None
        if not self.settings.enabled or self.settings.provider == "offline":
            logger.debug("Tier 2 LLM is disabled or set to offline.")
            return None

        # 2. Tier 2: Cascade resolution
        strategy = self.settings.provider.lower().strip()

        if strategy in ("cascade", "default"):
            return self._resolve_cascade(text)

        if strategy == "agnes":
            res = self.agnes.resolve_intent(text)
            if res is not None:
                return res
            if self.settings.cascade_fallback:
                return self._resolve_cascade_fallback(text, skip_provider="agnes")
            return None

        if strategy in ("gemini", "gemini_turn"):
            res = self.gemini.resolve_intent(text)
            if res is not None:
                return res
            if self.settings.cascade_fallback:
                return self._resolve_cascade_fallback(text, skip_provider="gemini")
            return None

        if strategy == "ollama":
            res = self.ollama.resolve_intent(text)
            if res is not None:
                return res
            if self.settings.cascade_fallback:
                return self._resolve_cascade_fallback(text, skip_provider="ollama")
            return None

        # Fallback to cascade
        return self._resolve_cascade(text)

    async def resolve_intent_async(self, text: str) -> ActionRequest | None:
        """Resolve user intent asynchronously cascading through available tiers."""
        t1_result = self.tier1.resolve_intent(text)
        if t1_result is not None:
            return t1_result

        if not self.settings.enabled or self.settings.provider == "offline":
            return None

        strategy = self.settings.provider.lower().strip()

        if strategy in ("cascade", "default"):
            return await self._resolve_cascade_async(text)

        if strategy == "agnes":
            res = await self.agnes.resolve_intent_async(text)
            if res is not None:
                return res
            if self.settings.cascade_fallback:
                return await self._resolve_cascade_fallback_async(text, skip_provider="agnes")
            return None

        if strategy in ("gemini", "gemini_turn"):
            res = await self.gemini.resolve_intent_async(text)
            if res is not None:
                return res
            if self.settings.cascade_fallback:
                return await self._resolve_cascade_fallback_async(text, skip_provider="gemini")
            return None

        if strategy == "ollama":
            res = await self.ollama.resolve_intent_async(text)
            if res is not None:
                return res
            if self.settings.cascade_fallback:
                return await self._resolve_cascade_fallback_async(text, skip_provider="ollama")
            return None

        return await self._resolve_cascade_async(text)

    def _resolve_cascade(self, text: str) -> ActionRequest | None:
        """Cascade: Agnes 3.0 Flash -> Gemini 2.0 Flash -> Ollama."""
        # 1. Agnes 3.0 Flash (Primary: high capacity, fast, unlimited tokens)
        if self.agnes.is_available():
            logger.debug("Attempting Tier 2 Agnes 3.0 Flash resolution...")
            res = self.agnes.resolve_intent(text)
            if res is not None:
                logger.info("Resolved intent via Agnes 3.0 Flash: %s", res.action_id)
                return res
            logger.debug("Agnes resolution returned None or failed. Cascading...")

        # 2. Gemini Turn (Secondary cloud fallback)
        if self.gemini.is_available():
            logger.debug("Attempting Tier 2 Gemini Turn resolution...")
            res = self.gemini.resolve_intent(text)
            if res is not None:
                logger.info("Resolved intent via Gemini Turn: %s", res.action_id)
                return res
            logger.debug("Gemini resolution returned None or failed. Cascading...")

        # 3. Local Ollama (Tertiary local offline fallback)
        if self.ollama.is_available():
            logger.debug("Attempting Tier 2 Ollama resolution...")
            res = self.ollama.resolve_intent(text)
            if res is not None:
                logger.info("Resolved intent via local Ollama: %s", res.action_id)
                return res

        logger.debug("All Tier 2 cascade providers exhausted for query: '%s'", text)
        return None

    async def _resolve_cascade_async(self, text: str) -> ActionRequest | None:
        """Async Cascade: Agnes 3.0 Flash -> Gemini 2.0 Flash -> Ollama."""
        if self.agnes.is_available():
            res = await self.agnes.resolve_intent_async(text)
            if res is not None:
                return res

        if self.gemini.is_available():
            res = await self.gemini.resolve_intent_async(text)
            if res is not None:
                return res

        if self.ollama.is_available():
            res = await self.ollama.resolve_intent_async(text)
            if res is not None:
                return res

        return None

    def _resolve_cascade_fallback(self, text: str, skip_provider: str) -> ActionRequest | None:
        """Fallback to remaining providers when primary specified provider fails."""
        if skip_provider != "agnes" and self.agnes.is_available():
            res = self.agnes.resolve_intent(text)
            if res is not None:
                return res
        if skip_provider != "gemini" and self.gemini.is_available():
            res = self.gemini.resolve_intent(text)
            if res is not None:
                return res
        if skip_provider != "ollama" and self.ollama.is_available():
            res = self.ollama.resolve_intent(text)
            if res is not None:
                return res
        return None

    async def _resolve_cascade_fallback_async(
        self, text: str, skip_provider: str
    ) -> ActionRequest | None:
        """Async fallback to remaining providers."""
        if skip_provider != "agnes" and self.agnes.is_available():
            res = await self.agnes.resolve_intent_async(text)
            if res is not None:
                return res
        if skip_provider != "gemini" and self.gemini.is_available():
            res = await self.gemini.resolve_intent_async(text)
            if res is not None:
                return res
        if skip_provider != "ollama" and self.ollama.is_available():
            res = await self.ollama.resolve_intent_async(text)
            if res is not None:
                return res
        return None
