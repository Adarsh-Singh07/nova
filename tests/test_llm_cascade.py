"""Unit tests for CascadeIntentEngine (Tier 1 + multi-provider Tier 2 cascade)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from nova.core.actions import ActionID
from nova.core.interfaces import ActionRequest
from nova.core.settings import LLMSettings
from nova.llm.cascade import CascadeIntentEngine


def test_cascade_tier1_precedence() -> None:
    """Tier 1 local regex always takes immediate precedence (0ms local)."""
    settings = LLMSettings(enabled=True, provider="cascade")

    mock_t1 = MagicMock()
    t1_action = ActionRequest(
        action_id=ActionID.VOLUME_UP.value,
        feedback_phrase="Increasing volume.",
        raw_query="volume up",
    )
    mock_t1.resolve_intent.return_value = t1_action

    mock_agnes = MagicMock()
    mock_gemini = MagicMock()
    mock_ollama = MagicMock()

    engine = CascadeIntentEngine(
        settings=settings,
        tier1_engine=mock_t1,
        agnes_provider=mock_agnes,
        gemini_provider=mock_gemini,
        ollama_provider=mock_ollama,
    )

    res = engine.resolve_intent("volume up")
    assert res is not None
    assert res.action_id == ActionID.VOLUME_UP.value

    # Tier 2 providers must NOT be called when Tier 1 succeeds
    mock_agnes.resolve_intent.assert_not_called()
    mock_gemini.resolve_intent.assert_not_called()
    mock_ollama.resolve_intent.assert_not_called()


def test_cascade_disabled_or_offline() -> None:
    mock_t1 = MagicMock()
    mock_t1.resolve_intent.return_value = None

    mock_agnes = MagicMock()

    # Disabled
    s_disabled = LLMSettings(enabled=False, provider="cascade")
    e_disabled = CascadeIntentEngine(
        settings=s_disabled, tier1_engine=mock_t1, agnes_provider=mock_agnes
    )
    assert e_disabled.resolve_intent("hello") is None
    mock_agnes.resolve_intent.assert_not_called()

    # Offline provider
    s_offline = LLMSettings(enabled=True, provider="offline")
    e_offline = CascadeIntentEngine(
        settings=s_offline, tier1_engine=mock_t1, agnes_provider=mock_agnes
    )
    assert e_offline.resolve_intent("hello") is None
    mock_agnes.resolve_intent.assert_not_called()


def test_cascade_flow_agnes_primary() -> None:
    """Agnes is primary: if available and succeeds, returns immediately."""
    settings = LLMSettings(enabled=True, provider="cascade")

    mock_t1 = MagicMock()
    mock_t1.resolve_intent.return_value = None

    mock_agnes = MagicMock()
    mock_agnes.is_available.return_value = True
    agnes_action = ActionRequest(
        action_id=ActionID.WEB_SEARCH.value,
        parameters={"query": "Pitsport"},
        feedback_phrase="Searching for Pitsport.",
        raw_query="find pitsport",
    )
    mock_agnes.resolve_intent.return_value = agnes_action

    mock_gemini = MagicMock()
    mock_gemini.is_available.return_value = True
    mock_ollama = MagicMock()

    engine = CascadeIntentEngine(
        settings=settings,
        tier1_engine=mock_t1,
        agnes_provider=mock_agnes,
        gemini_provider=mock_gemini,
        ollama_provider=mock_ollama,
    )

    res = engine.resolve_intent("find pitsport")
    assert res is not None
    assert res.action_id == ActionID.WEB_SEARCH.value
    assert res.parameters["query"] == "Pitsport"

    mock_agnes.resolve_intent.assert_called_once()
    mock_gemini.resolve_intent.assert_not_called()
    mock_ollama.resolve_intent.assert_not_called()


def test_cascade_flow_agnes_fails_gemini_succeeds() -> None:
    """If Agnes fails (returns None), falls back to Gemini."""
    settings = LLMSettings(enabled=True, provider="cascade")

    mock_t1 = MagicMock()
    mock_t1.resolve_intent.return_value = None

    mock_agnes = MagicMock()
    mock_agnes.is_available.return_value = True
    mock_agnes.resolve_intent.return_value = None  # Failed

    mock_gemini = MagicMock()
    mock_gemini.is_available.return_value = True
    gemini_action = ActionRequest(
        action_id=ActionID.APP_LAUNCH.value,
        parameters={"app_name": "Brave"},
        feedback_phrase="Launching Brave.",
        raw_query="open brave browser",
    )
    mock_gemini.resolve_intent.return_value = gemini_action

    mock_ollama = MagicMock()

    engine = CascadeIntentEngine(
        settings=settings,
        tier1_engine=mock_t1,
        agnes_provider=mock_agnes,
        gemini_provider=mock_gemini,
        ollama_provider=mock_ollama,
    )

    res = engine.resolve_intent("open brave browser")
    assert res is not None
    assert res.action_id == ActionID.APP_LAUNCH.value

    mock_agnes.resolve_intent.assert_called_once()
    mock_gemini.resolve_intent.assert_called_once()
    mock_ollama.resolve_intent.assert_not_called()


def test_cascade_flow_gemini_fails_ollama_succeeds() -> None:
    """If Agnes and Gemini both fail, falls back to Ollama."""
    settings = LLMSettings(enabled=True, provider="cascade")

    mock_t1 = MagicMock()
    mock_t1.resolve_intent.return_value = None

    mock_agnes = MagicMock()
    mock_agnes.is_available.return_value = False  # No key / offline

    mock_gemini = MagicMock()
    mock_gemini.is_available.return_value = True
    mock_gemini.resolve_intent.return_value = None  # Gemini failed

    mock_ollama = MagicMock()
    mock_ollama.is_available.return_value = True
    ollama_action = ActionRequest(
        action_id=ActionID.KEYBOARD_TYPE.value,
        parameters={"text": "Test input"},
        feedback_phrase="Typing text.",
        raw_query="type test input",
    )
    mock_ollama.resolve_intent.return_value = ollama_action

    engine = CascadeIntentEngine(
        settings=settings,
        tier1_engine=mock_t1,
        agnes_provider=mock_agnes,
        gemini_provider=mock_gemini,
        ollama_provider=mock_ollama,
    )

    res = engine.resolve_intent("type test input")
    assert res is not None
    assert res.action_id == ActionID.KEYBOARD_TYPE.value
    assert res.parameters["text"] == "Test input"

    mock_gemini.resolve_intent.assert_called_once()
    mock_ollama.resolve_intent.assert_called_once()


def test_cascade_async_flow() -> None:
    import asyncio

    async def _run() -> None:
        settings = LLMSettings(enabled=True, provider="cascade")

        mock_t1 = MagicMock()
        mock_t1.resolve_intent.return_value = None

        mock_agnes = MagicMock()
        mock_agnes.is_available.return_value = True
        action = ActionRequest(
            action_id=ActionID.CONVERSATION_REPLY.value,
            parameters={"reply": "Async test reply"},
            feedback_phrase="Async test reply",
            raw_query="hello async",
        )
        mock_agnes.resolve_intent_async = AsyncMock(return_value=action)

        engine = CascadeIntentEngine(
            settings=settings,
            tier1_engine=mock_t1,
            agnes_provider=mock_agnes,
        )

        res = await engine.resolve_intent_async("hello async")
        assert res is not None
        assert res.action_id == ActionID.CONVERSATION_REPLY.value
        assert res.parameters["reply"] == "Async test reply"

    asyncio.run(_run())


def test_cascade_provider_specific_modes() -> None:
    mock_t1 = MagicMock()
    mock_t1.resolve_intent.return_value = None

    mock_action = ActionRequest(
        action_id=ActionID.VOLUME_UP.value,
        feedback_phrase="Vol up",
        raw_query="vol up",
    )

    # 1. agnes mode
    mock_agnes = MagicMock()
    mock_agnes.resolve_intent.return_value = mock_action
    s_agnes = LLMSettings(enabled=True, provider="agnes", cascade_fallback=True)
    e_agnes = CascadeIntentEngine(settings=s_agnes, tier1_engine=mock_t1, agnes_provider=mock_agnes)
    assert e_agnes.resolve_intent("vol up") == mock_action

    # 1b. agnes fails, fallback disabled
    mock_agnes.resolve_intent.return_value = None
    s_agnes_nofb = LLMSettings(enabled=True, provider="agnes", cascade_fallback=False)
    e_agnes_nofb = CascadeIntentEngine(
        settings=s_agnes_nofb, tier1_engine=mock_t1, agnes_provider=mock_agnes
    )
    assert e_agnes_nofb.resolve_intent("vol up") is None

    # 1c. agnes fails, fallback enabled -> gemini succeeds
    mock_gemini = MagicMock()
    mock_gemini.is_available.return_value = True
    mock_gemini.resolve_intent.return_value = mock_action
    e_agnes_fb = CascadeIntentEngine(
        settings=s_agnes,
        tier1_engine=mock_t1,
        agnes_provider=mock_agnes,
        gemini_provider=mock_gemini,
    )
    assert e_agnes_fb.resolve_intent("vol up") == mock_action

    # 2. gemini mode
    s_gemini = LLMSettings(enabled=True, provider="gemini", cascade_fallback=True)
    e_gemini = CascadeIntentEngine(
        settings=s_gemini, tier1_engine=mock_t1, gemini_provider=mock_gemini
    )
    assert e_gemini.resolve_intent("vol up") == mock_action

    # 2b. gemini fails, fallback enabled -> agnes succeeds
    mock_gemini.resolve_intent.return_value = None
    mock_agnes.is_available.return_value = True
    mock_agnes.resolve_intent.return_value = mock_action
    e_gemini_fb = CascadeIntentEngine(
        settings=s_gemini,
        tier1_engine=mock_t1,
        agnes_provider=mock_agnes,
        gemini_provider=mock_gemini,
    )
    assert e_gemini_fb.resolve_intent("vol up") == mock_action

    # 2c. gemini fails, fallback disabled
    s_gemini_nofb = LLMSettings(enabled=True, provider="gemini", cascade_fallback=False)
    e_gemini_nofb = CascadeIntentEngine(
        settings=s_gemini_nofb, tier1_engine=mock_t1, gemini_provider=mock_gemini
    )
    assert e_gemini_nofb.resolve_intent("vol up") is None

    # 3. ollama mode
    mock_ollama = MagicMock()
    mock_ollama.is_available.return_value = True
    mock_ollama.resolve_intent.return_value = mock_action
    s_ollama = LLMSettings(enabled=True, provider="ollama", cascade_fallback=True)
    e_ollama = CascadeIntentEngine(
        settings=s_ollama, tier1_engine=mock_t1, ollama_provider=mock_ollama
    )
    assert e_ollama.resolve_intent("vol up") == mock_action

    # 3b. ollama fails, fallback enabled -> agnes succeeds
    mock_ollama.resolve_intent.return_value = None
    e_ollama_fb = CascadeIntentEngine(
        settings=s_ollama,
        tier1_engine=mock_t1,
        agnes_provider=mock_agnes,
        ollama_provider=mock_ollama,
    )
    assert e_ollama_fb.resolve_intent("vol up") == mock_action

    # 3c. ollama fails, fallback disabled
    s_ollama_nofb = LLMSettings(enabled=True, provider="ollama", cascade_fallback=False)
    e_ollama_nofb = CascadeIntentEngine(
        settings=s_ollama_nofb, tier1_engine=mock_t1, ollama_provider=mock_ollama
    )
    assert e_ollama_nofb.resolve_intent("vol up") is None


def test_cascade_async_specific_modes() -> None:
    import asyncio

    async def _run() -> None:
        mock_t1 = MagicMock()
        mock_t1.resolve_intent.return_value = None

        mock_action = ActionRequest(
            action_id=ActionID.MEDIA_PLAY_PAUSE.value,
            feedback_phrase="play",
            raw_query="play",
        )

        mock_agnes = MagicMock()
        mock_agnes.is_available.return_value = True
        mock_agnes.resolve_intent_async = AsyncMock(return_value=mock_action)

        mock_gemini = MagicMock()
        mock_gemini.is_available.return_value = True
        mock_gemini.resolve_intent_async = AsyncMock(return_value=mock_action)

        mock_ollama = MagicMock()
        mock_ollama.is_available.return_value = True
        mock_ollama.resolve_intent_async = AsyncMock(return_value=mock_action)

        # agnes mode
        s_agnes = LLMSettings(enabled=True, provider="agnes", cascade_fallback=True)
        e_agnes = CascadeIntentEngine(
            settings=s_agnes, tier1_engine=mock_t1, agnes_provider=mock_agnes
        )
        assert await e_agnes.resolve_intent_async("play") == mock_action

        # agnes fails -> gemini async fallback
        mock_agnes.resolve_intent_async = AsyncMock(return_value=None)
        e_agnes_fb = CascadeIntentEngine(
            settings=s_agnes,
            tier1_engine=mock_t1,
            agnes_provider=mock_agnes,
            gemini_provider=mock_gemini,
        )
        assert await e_agnes_fb.resolve_intent_async("play") == mock_action

        # gemini mode
        s_gemini = LLMSettings(enabled=True, provider="gemini", cascade_fallback=True)
        e_gemini = CascadeIntentEngine(
            settings=s_gemini, tier1_engine=mock_t1, gemini_provider=mock_gemini
        )
        assert await e_gemini.resolve_intent_async("play") == mock_action

        # ollama mode
        s_ollama = LLMSettings(enabled=True, provider="ollama", cascade_fallback=True)
        e_ollama = CascadeIntentEngine(
            settings=s_ollama, tier1_engine=mock_t1, ollama_provider=mock_ollama
        )
        assert await e_ollama.resolve_intent_async("play") == mock_action

        # offline async
        s_offline = LLMSettings(enabled=True, provider="offline")
        e_offline = CascadeIntentEngine(settings=s_offline, tier1_engine=mock_t1)
        assert await e_offline.resolve_intent_async("play") is None

        # cascade all fail async
        mock_agnes.resolve_intent_async = AsyncMock(return_value=None)
        mock_gemini.resolve_intent_async = AsyncMock(return_value=None)
        mock_ollama.resolve_intent_async = AsyncMock(return_value=None)
        s_cascade = LLMSettings(enabled=True, provider="cascade")
        e_cascade = CascadeIntentEngine(
            settings=s_cascade,
            tier1_engine=mock_t1,
            agnes_provider=mock_agnes,
            gemini_provider=mock_gemini,
            ollama_provider=mock_ollama,
        )
        assert await e_cascade.resolve_intent_async("play") is None

    asyncio.run(_run())
