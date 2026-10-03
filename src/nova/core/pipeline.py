"""Core interaction pipeline coordinator for NOVA.

Orchestrates audio capture/text -> STT -> Intent classification -> Security Allowlist
-> User Confirmation -> Platform Execution -> TTS response.
"""

from __future__ import annotations

import logging
import urllib.parse
from dataclasses import dataclass
from typing import Any

import numpy as np

from nova.core.actions import ActionID, AllowlistValidator
from nova.core.interfaces import (
    ActionRequest,
    ActionResult,
    ConfirmationHandlerProtocol,
    IntentEngineProtocol,
    PlatformAdapterProtocol,
    STTEngineProtocol,
    TTSEngineProtocol,
)
from nova.core.settings import NovaSettings
from nova.core.state import PipelineState, PipelineStateMachine

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineTurnResult:
    """Complete summary of a single interaction turn."""

    query: str
    action_request: ActionRequest | None
    action_result: ActionResult | None
    spoken_feedback: str
    success: bool
    error: str | None = None


class NovaPipeline:
    """Central coordinator for the NOVA voice and text assistant pipeline."""

    def __init__(
        self,
        state_machine: PipelineStateMachine | None = None,
        stt: STTEngineProtocol | None = None,
        intent_engine: IntentEngineProtocol | None = None,
        tts: TTSEngineProtocol | None = None,
        platform: PlatformAdapterProtocol | None = None,
        settings: NovaSettings | None = None,
        confirmation_handler: ConfirmationHandlerProtocol | None = None,
        *,
        stt_engine: STTEngineProtocol | None = None,
        tts_engine: TTSEngineProtocol | None = None,
        platform_adapter: PlatformAdapterProtocol | None = None,
    ) -> None:
        from nova.core.fakes import (
            FakeIntentEngine,
            FakePlatformAdapter,
            FakeSTTEngine,
            FakeTTSEngine,
        )

        self.state_machine = state_machine or PipelineStateMachine()
        self.stt = stt or stt_engine or FakeSTTEngine()
        self.tts = tts or tts_engine or FakeTTSEngine()
        self.platform = platform or platform_adapter or FakePlatformAdapter()
        self.intent_engine = intent_engine or FakeIntentEngine()
        self.settings = settings or NovaSettings()
        self.confirmation_handler = confirmation_handler

    def process_audio(self, audio_data: np.ndarray[Any, Any]) -> PipelineTurnResult:
        """Execute a full turn starting from raw audio PCM data."""
        try:
            self.state_machine.transition_to(PipelineState.LISTENING)
            self.state_machine.transition_to(PipelineState.TRANSCRIBING)

            transcription = self.stt.transcribe(audio_data)
            text = transcription.text.strip()

            if not text:
                logger.info("No speech recognized in audio buffer.")
                self.state_machine.transition_to(PipelineState.IDLE)
                return PipelineTurnResult(
                    query="",
                    action_request=None,
                    action_result=None,
                    spoken_feedback="",
                    success=False,
                    error="No speech detected",
                )

            return self._process_text_internal(text)

        except Exception as e:
            return self._handle_error(e, query="<audio>")

    def process_text(self, text: str) -> PipelineTurnResult:
        """Execute a full turn directly from text (for CLI --text and accessibility box)."""
        clean_text = text.strip()
        if not clean_text:
            return PipelineTurnResult(
                query="",
                action_request=None,
                action_result=None,
                spoken_feedback="",
                success=False,
                error="Empty text command",
            )

        try:
            # Check for compound actions
            if hasattr(self.intent_engine, "resolve_compound"):
                compound_reqs = self.intent_engine.resolve_compound(clean_text)
                if len(compound_reqs) > 1:
                    last_turn: PipelineTurnResult | None = None
                    feedback_items: list[str] = []
                    for req in compound_reqs:
                        turn = self._process_action_request(req, clean_text)
                        last_turn = turn
                        if turn.spoken_feedback:
                            feedback_items.append(turn.spoken_feedback)
                        if not turn.success:
                            break
                    combined_feedback = " and ".join(feedback_items) if feedback_items else ""
                    return PipelineTurnResult(
                        query=clean_text,
                        action_request=last_turn.action_request if last_turn else None,
                        action_result=last_turn.action_result if last_turn else None,
                        spoken_feedback=combined_feedback,
                        success=last_turn.success if last_turn else False,
                        error=last_turn.error if last_turn else None,
                    )

            return self._process_text_internal(clean_text)
        except Exception as e:
            return self._handle_error(e, query=clean_text)

    def _process_text_internal(self, text: str) -> PipelineTurnResult:
        """Internal processing pipeline after text is obtained."""
        self.state_machine.transition_to(PipelineState.THINKING)
        logger.info("Processing command: '%s'", text)

        # 1. Intent Resolution
        action_req = self.intent_engine.resolve_intent(text)
        if action_req is None:
            logger.info("Intent could not be resolved for query: '%s'", text)
            feedback = "I did not understand that command."
            self.state_machine.transition_to(PipelineState.SPEAKING)
            self.tts.synthesize(feedback)
            self.state_machine.transition_to(PipelineState.IDLE)
            return PipelineTurnResult(
                query=text,
                action_request=None,
                action_result=None,
                spoken_feedback=feedback,
                success=False,
                error="Unknown intent",
            )

        return self._process_action_request(action_req, text)

    def _process_action_request(self, action_req: ActionRequest, text: str) -> PipelineTurnResult:
        """Process, validate, confirm, execute, and speak a resolved ActionRequest."""
        # 2. Strict Allowlist Validation (Rule R5)
        AllowlistValidator.validate(action_req)

        # 3. Confirmation Policy Gate
        if action_req.is_destructive and not self.settings.security.fast_mode:
            self.state_machine.transition_to(PipelineState.AWAITING_CONFIRMATION)
            confirmed = False
            if self.confirmation_handler is not None:
                confirmed = self.confirmation_handler.request_confirmation(action_req)

            if not confirmed:
                logger.info("Action '%s' was rejected or timed out.", action_req.action_id)
                feedback = "Action cancelled."
                self.state_machine.transition_to(PipelineState.SPEAKING)
                self.tts.synthesize(feedback)
                self.state_machine.transition_to(PipelineState.IDLE)
                return PipelineTurnResult(
                    query=text,
                    action_request=action_req,
                    action_result=None,
                    spoken_feedback=feedback,
                    success=False,
                    error="Action cancelled by user",
                )

        # 4. Action Execution via Platform Adapter
        self.state_machine.transition_to(PipelineState.ACTING)
        action_res = self._execute_platform_action(action_req)

        # 5. Spoken Reply reflecting real outcome
        feedback_text = action_res.message if action_res.message else action_req.feedback_phrase
        self.state_machine.transition_to(PipelineState.SPEAKING)
        self.tts.synthesize(feedback_text)
        self.state_machine.transition_to(PipelineState.IDLE)

        return PipelineTurnResult(
            query=text,
            action_request=action_req,
            action_result=action_res,
            spoken_feedback=feedback_text,
            success=action_res.success,
            error=action_res.error,
        )

    def _execute_platform_action(self, request: ActionRequest) -> ActionResult:
        """Route allowlisted ActionRequest to the platform adapter."""
        action_id = request.action_id
        params = request.parameters

        if action_id == ActionID.VOLUME_UP.value:
            current = self.platform.get_volume()
            return self.platform.set_volume(min(100, current + 10))

        if action_id == ActionID.VOLUME_DOWN.value:
            current = self.platform.get_volume()
            return self.platform.set_volume(max(0, current - 10))

        if action_id == ActionID.VOLUME_SET.value:
            percent = int(params["percent"])
            return self.platform.set_volume(percent)

        if action_id == ActionID.VOLUME_MUTE_TOGGLE.value:
            return self.platform.toggle_mute()

        if action_id == ActionID.MEDIA_PLAY_PAUSE.value:
            return self.platform.media_play_pause()

        if action_id == ActionID.MEDIA_NEXT.value:
            return self.platform.media_next()

        if action_id == ActionID.MEDIA_PREVIOUS.value:
            return self.platform.media_previous()

        if action_id == ActionID.MEDIA_STOP.value:
            return self.platform.media_stop()

        if action_id == ActionID.SYSTEM_LOCK.value:
            return self.platform.lock_workstation()

        if action_id == ActionID.SYSTEM_SLEEP.value:
            return self.platform.suspend_system()

        if action_id == ActionID.APP_LAUNCH.value:
            return self.platform.launch_app(str(params["app_name"]))

        if action_id == ActionID.APP_CLOSE.value:
            return self.platform.close_app(str(params["app_name"]))

        if action_id == ActionID.DARK_MODE_TOGGLE.value:
            return self.platform.toggle_dark_mode()

        if action_id == ActionID.WEB_SEARCH.value:
            encoded = urllib.parse.quote_plus(str(params["query"]))
            return self.platform.open_url(f"https://www.google.com/search?q={encoded}")

        if action_id == ActionID.WEB_OPEN_URL.value:
            return self.platform.open_url(str(params["url"]))

        if action_id == ActionID.TIMER_SET:
            duration = float(params.get("duration_seconds", 60.0))
            return ActionResult(
                success=True,
                message=f"Timer set for {int(duration)} seconds.",
                data={"duration_seconds": duration},
            )

        if action_id in (
            ActionID.STOPWATCH_START.value,
            ActionID.STOPWATCH_STOP.value,
            ActionID.STOPWATCH_RESET.value,
            ActionID.STOPWATCH_STATUS.value,
        ):
            msg_map = {
                ActionID.STOPWATCH_START.value: "Stopwatch started.",
                ActionID.STOPWATCH_STOP.value: "Stopwatch stopped.",
                ActionID.STOPWATCH_RESET.value: "Stopwatch reset.",
                ActionID.STOPWATCH_STATUS.value: "Stopwatch is running.",
            }
            return ActionResult(success=True, message=msg_map[action_id])

        if action_id == ActionID.REMINDER_SET.value:
            return ActionResult(
                success=True,
                message=f"Reminder set for {params.get('text')}.",
                data=params,
            )

        if action_id == ActionID.NOTE_APPEND.value:
            return ActionResult(
                success=True,
                message="Saved your note.",
                data=params,
            )

        if action_id == ActionID.VOLUME_APP_SET.value:
            app = str(params.get("app_name", ""))
            pct = int(params.get("percent", 50))
            return self.platform.set_app_volume(app, pct)

        if action_id == ActionID.CONVERSATION_REPLY.value:
            return ActionResult(
                success=True,
                message=str(params.get("reply", request.feedback_phrase)),
            )

        return ActionResult(
            success=False,
            message="Unsupported action execution",
            error=f"Unimplemented allowlisted action: {action_id}",
        )

    def cancel(self) -> None:
        """Interrupt active TTS or execution and reset to IDLE."""
        logger.info("Cancelling active pipeline operation.")
        self.tts.stop()
        self.state_machine.reset()

    def _handle_error(self, error: Exception, query: str) -> PipelineTurnResult:
        """Handle errors gracefully without exposing stack traces to the user (Rule R6)."""
        logger.exception("Pipeline execution error during query '%s'", query)
        self.state_machine.reset()
        error_msg = "An error occurred while processing your request."
        try:
            self.state_machine.transition_to(PipelineState.ERROR)
            self.state_machine.transition_to(PipelineState.SPEAKING)
            self.tts.synthesize(error_msg)
            self.state_machine.transition_to(PipelineState.IDLE)
        except Exception:
            self.state_machine.reset()

        return PipelineTurnResult(
            query=query,
            action_request=None,
            action_result=None,
            spoken_feedback=error_msg,
            success=False,
            error=str(error),
        )
