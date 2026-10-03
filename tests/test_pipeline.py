"""Integration and unit tests for the NovaPipeline coordinator using fakes."""

from __future__ import annotations

import numpy as np
import pytest

from nova.core.actions import ActionID
from nova.core.fakes import (
    FakeConfirmationHandler,
    FakeIntentEngine,
    FakePlatformAdapter,
    FakeSTTEngine,
    FakeTTSEngine,
)
from nova.core.pipeline import NovaPipeline
from nova.core.settings import NovaSettings
from nova.core.state import PipelineState, PipelineStateMachine


@pytest.fixture
def pipeline_env() -> tuple[NovaPipeline, FakePlatformAdapter, FakeTTSEngine, PipelineStateMachine]:
    sm = PipelineStateMachine()
    stt = FakeSTTEngine(default_text="turn volume up")
    intent = FakeIntentEngine()
    tts = FakeTTSEngine()
    platform = FakePlatformAdapter()
    settings = NovaSettings()
    confirmation = FakeConfirmationHandler(auto_confirm=True)

    pipeline = NovaPipeline(
        state_machine=sm,
        stt=stt,
        intent_engine=intent,
        tts=tts,
        platform=platform,
        settings=settings,
        confirmation_handler=confirmation,
    )
    return pipeline, platform, tts, sm


def test_process_audio_success(
    pipeline_env: tuple[NovaPipeline, FakePlatformAdapter, FakeTTSEngine, PipelineStateMachine],
) -> None:
    pipeline, platform, tts, sm = pipeline_env
    dummy_audio = np.zeros(16000, dtype=np.float32)

    initial_vol = platform.get_volume()
    res = pipeline.process_audio(dummy_audio)

    assert res.success is True
    assert res.query == "turn volume up"
    assert res.action_request is not None
    assert res.action_request.action_id == ActionID.VOLUME_UP.value
    assert platform.get_volume() == initial_vol + 10
    assert len(tts.synthesized_phrases) == 1
    assert sm.current_state == PipelineState.IDLE


def test_process_audio_empty_speech(
    pipeline_env: tuple[NovaPipeline, FakePlatformAdapter, FakeTTSEngine, PipelineStateMachine],
) -> None:
    pipeline, _, _, sm = pipeline_env
    # Configure STT to return empty transcript
    pipeline.stt = FakeSTTEngine(default_text="")
    dummy_audio = np.zeros(16000, dtype=np.float32)

    res = pipeline.process_audio(dummy_audio)
    assert res.success is False
    assert res.error == "No speech detected"
    assert sm.current_state == PipelineState.IDLE


def test_process_text_commands(
    pipeline_env: tuple[NovaPipeline, FakePlatformAdapter, FakeTTSEngine, PipelineStateMachine],
) -> None:
    pipeline, platform, _tts, sm = pipeline_env

    # 1. Volume down
    res = pipeline.process_text("turn volume down")
    assert res.success is True
    assert res.action_request is not None
    assert res.action_request.action_id == ActionID.VOLUME_DOWN.value

    # 2. Set volume to specific number
    res = pipeline.process_text("set volume to 80")
    assert res.success is True
    assert platform.get_volume() == 80

    # 3. Mute
    res = pipeline.process_text("mute audio")
    assert res.success is True
    assert platform.is_muted is True

    # 4. Media play/pause
    res = pipeline.process_text("pause music")
    assert res.success is True
    assert res.action_request is not None
    assert res.action_request.action_id == ActionID.MEDIA_PLAY_PAUSE.value

    # 5. Media next & previous
    res = pipeline.process_text("next song")
    assert res.success is True
    res = pipeline.process_text("previous track")
    assert res.success is True

    # 6. Launch app
    res = pipeline.process_text("open spotify")
    assert res.success is True
    assert "spotify" in platform.launched_apps

    # 7. Dark mode
    res = pipeline.process_text("toggle dark mode")
    assert res.success is True

    # 8. Web search
    res = pipeline.process_text("search for python dataclasses")
    assert res.success is True
    assert len(platform.opened_urls) == 1
    assert "dataclasses" in platform.opened_urls[0]

    assert sm.current_state == PipelineState.IDLE


def test_process_empty_text(
    pipeline_env: tuple[NovaPipeline, FakePlatformAdapter, FakeTTSEngine, PipelineStateMachine],
) -> None:
    pipeline, _, _, sm = pipeline_env
    res = pipeline.process_text("   ")
    assert res.success is False
    assert res.error == "Empty text command"
    assert sm.current_state == PipelineState.IDLE


def test_unknown_intent(
    pipeline_env: tuple[NovaPipeline, FakePlatformAdapter, FakeTTSEngine, PipelineStateMachine],
) -> None:
    pipeline, _, tts, sm = pipeline_env

    # Mock intent engine returning None
    class EmptyIntentEngine(FakeIntentEngine):
        def resolve_intent(self, text: str) -> None:
            return None

    pipeline.intent_engine = EmptyIntentEngine()
    res = pipeline.process_text("blah blah completely unrecognized")

    assert res.success is False
    assert res.error == "Unknown intent"
    assert "I did not understand that command." in tts.synthesized_phrases
    assert sm.current_state == PipelineState.IDLE


def test_destructive_action_confirmation_accepted(
    pipeline_env: tuple[NovaPipeline, FakePlatformAdapter, FakeTTSEngine, PipelineStateMachine],
) -> None:
    pipeline, platform, _, sm = pipeline_env
    pipeline.confirmation_handler = FakeConfirmationHandler(auto_confirm=True)

    res = pipeline.process_text("lock screen")
    assert res.success is True
    assert platform.is_locked is True
    assert sm.current_state == PipelineState.IDLE


def test_destructive_action_confirmation_rejected(
    pipeline_env: tuple[NovaPipeline, FakePlatformAdapter, FakeTTSEngine, PipelineStateMachine],
) -> None:
    pipeline, platform, tts, sm = pipeline_env
    pipeline.confirmation_handler = FakeConfirmationHandler(auto_confirm=False)

    res = pipeline.process_text("lock screen")
    assert res.success is False
    assert res.error == "Action cancelled by user"
    assert platform.is_locked is False
    assert "Action cancelled." in tts.synthesized_phrases
    assert sm.current_state == PipelineState.IDLE


def test_destructive_action_fast_mode(
    pipeline_env: tuple[NovaPipeline, FakePlatformAdapter, FakeTTSEngine, PipelineStateMachine],
) -> None:
    pipeline, platform, _, sm = pipeline_env
    pipeline.settings.security.fast_mode = True
    # Even with auto_confirm=False, fast_mode bypasses the gate
    pipeline.confirmation_handler = FakeConfirmationHandler(auto_confirm=False)

    res = pipeline.process_text("lock screen")
    assert res.success is True
    assert platform.is_locked is True
    assert sm.current_state == PipelineState.IDLE


def test_pipeline_cancellation(
    pipeline_env: tuple[NovaPipeline, FakePlatformAdapter, FakeTTSEngine, PipelineStateMachine],
) -> None:
    pipeline, _, tts, sm = pipeline_env
    sm.transition_to(PipelineState.LISTENING)

    pipeline.cancel()
    assert tts.stop_called_count == 1
    assert sm.current_state == PipelineState.IDLE


def test_pipeline_error_handling(
    pipeline_env: tuple[NovaPipeline, FakePlatformAdapter, FakeTTSEngine, PipelineStateMachine],
) -> None:
    pipeline, _, tts, sm = pipeline_env

    # Force an exception inside the intent engine
    class FaultyIntentEngine(FakeIntentEngine):
        def resolve_intent(self, text: str) -> None:
            raise RuntimeError("Engine hardware failure")

    pipeline.intent_engine = FaultyIntentEngine()
    res = pipeline.process_text("turn volume up")

    assert res.success is False
    assert "Engine hardware failure" in str(res.error)
    assert any("error occurred" in p for p in tts.synthesized_phrases)
    assert sm.current_state == PipelineState.IDLE


def test_pipeline_on_reply_ready_callback() -> None:
    emitted_replies: list[str] = []
    tts = FakeTTSEngine()
    pipeline = NovaPipeline(
        tts=tts,
        on_reply_ready=emitted_replies.append,
    )
    res = pipeline.process_text("turn volume up")
    assert res.success is True
    assert len(emitted_replies) == 1
    assert "volume" in emitted_replies[0].lower()
    assert len(tts.spoken_phrases) == 1
