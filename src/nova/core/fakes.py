"""Fakes and test doubles for NOVA core subsystems.

Provides deterministic, zero-dependency implementations of STT, Intent, TTS,
and Platform adapters for unit testing and headless --text CLI execution.
"""

from __future__ import annotations

import os
import re
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
    TranscriptionResult,
    TTSEngineProtocol,
)


class FakeSTTEngine(STTEngineProtocol):
    """Deterministic Speech-to-Text fake returning pre-configured transcripts."""

    def __init__(self, default_text: str = "turn volume up") -> None:
        self.default_text = default_text
        self.transcribed_calls: list[np.ndarray[Any, Any]] = []
        self._available = True

    def transcribe(self, audio_data: np.ndarray[Any, Any]) -> TranscriptionResult:
        self.transcribed_calls.append(audio_data)
        return TranscriptionResult(
            text=self.default_text,
            confidence=0.98,
            language="en",
            duration_seconds=float(len(audio_data)) / 16000.0 if len(audio_data) > 0 else 1.0,
        )

    def is_available(self) -> bool:
        return self._available

    def set_available(self, available: bool) -> None:
        self._available = available


class FakeIntentEngine(IntentEngineProtocol):
    """Deterministic intent engine supporting primary built-in voice commands."""

    def resolve_intent(self, text: str) -> ActionRequest | None:
        clean = text.strip().lower()
        if not clean:
            return None

        # Volume controls
        if "volume up" in clean:
            req = ActionRequest(
                action_id=ActionID.VOLUME_UP.value,
                feedback_phrase="Turning volume up.",
                raw_query=text,
            )
            AllowlistValidator.validate(req)
            return req

        if "volume down" in clean:
            req = ActionRequest(
                action_id=ActionID.VOLUME_DOWN.value,
                feedback_phrase="Turning volume down.",
                raw_query=text,
            )
            AllowlistValidator.validate(req)
            return req

        vol_match = re.search(r"(?:set volume to|volume)\s+(\d+)", clean)
        if vol_match:
            percent = int(vol_match.group(1))
            req = ActionRequest(
                action_id=ActionID.VOLUME_SET.value,
                parameters={"percent": percent},
                feedback_phrase=f"Setting volume to {percent} percent.",
                raw_query=text,
            )
            AllowlistValidator.validate(req)
            return req

        if "mute" in clean:
            req = ActionRequest(
                action_id=ActionID.VOLUME_MUTE_TOGGLE.value,
                feedback_phrase="Toggling mute.",
                raw_query=text,
            )
            AllowlistValidator.validate(req)
            return req

        # Media controls
        if any(w in clean for w in ["play", "pause", "resume"]):
            req = ActionRequest(
                action_id=ActionID.MEDIA_PLAY_PAUSE.value,
                feedback_phrase="Toggled media playback.",
                raw_query=text,
            )
            AllowlistValidator.validate(req)
            return req

        if "next" in clean:
            req = ActionRequest(
                action_id=ActionID.MEDIA_NEXT.value,
                feedback_phrase="Playing next track.",
                raw_query=text,
            )
            AllowlistValidator.validate(req)
            return req

        if "previous" in clean:
            req = ActionRequest(
                action_id=ActionID.MEDIA_PREVIOUS.value,
                feedback_phrase="Playing previous track.",
                raw_query=text,
            )
            AllowlistValidator.validate(req)
            return req

        # System controls (Destructive)
        if "lock" in clean:
            req = ActionRequest(
                action_id=ActionID.SYSTEM_LOCK.value,
                is_destructive=True,
                feedback_phrase="Locking workstation.",
                raw_query=text,
            )
            AllowlistValidator.validate(req)
            return req

        if "sleep" in clean:
            req = ActionRequest(
                action_id=ActionID.SYSTEM_SLEEP.value,
                is_destructive=True,
                feedback_phrase="Suspending system.",
                raw_query=text,
            )
            AllowlistValidator.validate(req)
            return req

        # Web search
        search_match = re.search(r"\b(?:search for|google)\s+(.+)", clean)
        if search_match:
            query = search_match.group(1).strip()
            req = ActionRequest(
                action_id=ActionID.WEB_SEARCH.value,
                parameters={"query": query},
                feedback_phrase=f"Searching for {query}.",
                raw_query=text,
            )
            AllowlistValidator.validate(req)
            return req

        # App controls
        open_match = re.search(r"^\s*(?:open|launch)\s+([a-zA-Z0-9_\-\.\s]+)", clean)
        if open_match:
            app_name = open_match.group(1).strip()
            req = ActionRequest(
                action_id=ActionID.APP_LAUNCH.value,
                parameters={"app_name": app_name},
                feedback_phrase=f"Opening {app_name}.",
                raw_query=text,
            )
            AllowlistValidator.validate(req)
            return req

        close_match = re.search(r"^\s*(?:close|quit)\s+([a-zA-Z0-9_\-\.\s]+)", clean)
        if close_match:
            app_name = close_match.group(1).strip()
            req = ActionRequest(
                action_id=ActionID.APP_CLOSE.value,
                parameters={"app_name": app_name},
                is_destructive=True,
                feedback_phrase=f"Closing {app_name}.",
                raw_query=text,
            )
            AllowlistValidator.validate(req)
            return req

        # System appearance
        if "dark mode" in clean:
            req = ActionRequest(
                action_id=ActionID.DARK_MODE_TOGGLE.value,
                feedback_phrase="Toggling dark mode.",
                raw_query=text,
            )
            AllowlistValidator.validate(req)
            return req

        # Conversational fallback
        return ActionRequest(
            action_id=ActionID.CONVERSATION_REPLY.value,
            parameters={"reply": f"You said: {text}"},
            feedback_phrase=f"You said: {text}",
            raw_query=text,
        )


class FakeTTSEngine(TTSEngineProtocol):
    """In-memory Text-to-Speech double tracking synthesized phrases."""

    def __init__(self) -> None:
        self.synthesized_phrases: list[str] = []
        self.stop_called_count: int = 0

    def synthesize(self, text: str, voice: str | None = None) -> bytes:
        self.synthesized_phrases.append(text)
        # Return a mock 44-byte standard RIFF/WAV header
        return b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"

    def stop(self) -> None:
        self.stop_called_count += 1


class FakePlatformAdapter(PlatformAdapterProtocol):
    """In-memory platform double recording OS actions without touching system state."""

    def __init__(self) -> None:
        self.volume: int = 50
        self.is_muted: bool = False
        self.media_playing: bool = True
        self.is_locked: bool = False
        self.is_suspended: bool = False
        self.dark_mode: bool = True
        self.launched_apps: list[str] = []
        self.closed_apps: list[str] = []
        self.opened_urls: list[str] = []
        self.typed_texts: list[str] = []
        self.pressed_keys: list[str] = []
        self.process_unmuted = False

    def set_volume(self, percent: int) -> ActionResult:
        self.volume = max(0, min(100, percent))
        return ActionResult(success=True, message=f"Volume set to {self.volume}%")

    def get_volume(self) -> int:
        return self.volume

    def toggle_mute(self) -> ActionResult:
        self.is_muted = not self.is_muted
        return ActionResult(
            success=True, message=f"Mute {'enabled' if self.is_muted else 'disabled'}"
        )

    def media_play_pause(self) -> ActionResult:
        self.media_playing = not self.media_playing
        return ActionResult(success=True, message="Media playback toggled")

    def media_next(self) -> ActionResult:
        return ActionResult(success=True, message="Media skipped to next")

    def media_previous(self) -> ActionResult:
        return ActionResult(success=True, message="Media skipped to previous")

    def media_stop(self) -> ActionResult:
        self.media_playing = False
        return ActionResult(success=True, message="Media playback stopped")

    def set_app_volume(self, app_name: str, percent: int) -> ActionResult:
        return ActionResult(
            success=True,
            message=f"Adjusted volume for {app_name} to {percent}%.",
            data={"app_name": app_name, "percent": percent},
        )

    def lock_workstation(self) -> ActionResult:
        self.is_locked = True
        return ActionResult(success=True, message="Workstation locked")

    def suspend_system(self) -> ActionResult:
        self.is_suspended = True
        return ActionResult(success=True, message="System suspended")

    def launch_app(self, app_name_or_target: str) -> ActionResult:
        self.launched_apps.append(app_name_or_target)
        return ActionResult(success=True, message=f"Launched {app_name_or_target}")

    def close_app(self, app_name_or_target: str) -> ActionResult:
        lower = app_name_or_target.lower().strip()
        stem, _ = os.path.splitext(lower)
        if lower in (
            "explorer.exe",
            "system",
            "csrss.exe",
            "systemd",
            "kwin",
            "nova",
            "nova.exe",
        ) or stem in ("explorer", "nova"):
            return ActionResult(
                success=False,
                message=f"Refused to terminate protected system process: '{app_name_or_target}'.",
                error="Critical process protection",
            )
        self.closed_apps.append(app_name_or_target)
        return ActionResult(success=True, message=f"Closed {app_name_or_target}")

    def toggle_dark_mode(self) -> ActionResult:
        self.dark_mode = not self.dark_mode
        return ActionResult(
            success=True, message=f"Dark mode {'enabled' if self.dark_mode else 'disabled'}"
        )

    def open_url(self, url: str) -> ActionResult:
        clean = url.strip()
        if not (clean.startswith("http://") or clean.startswith("https://")):
            return ActionResult(
                success=False,
                message=f"Refused to open invalid URL protocol: '{clean}'",
                error="Invalid URL protocol",
            )
        self.opened_urls.append(clean)
        return ActionResult(success=True, message=f"Opened {clean}")

    def type_text(self, text: str) -> ActionResult:
        self.typed_texts.append(text)
        return ActionResult(success=True, message=f"Typed text: {text}", data={"text": text})

    def press_key(self, key: str) -> ActionResult:
        clean_key = key.strip().lower()
        self.pressed_keys.append(clean_key)
        return ActionResult(
            success=True, message=f"Pressed {clean_key} key", data={"key": clean_key}
        )

    def unmute_current_process(self) -> None:
        self.process_unmuted = True


class FakeConfirmationHandler(ConfirmationHandlerProtocol):
    """Deterministic confirmation handler for testing confirmation gates."""

    def __init__(self, auto_confirm: bool = True) -> None:
        self.auto_confirm = auto_confirm
        self.prompted_actions: list[ActionRequest] = []

    def request_confirmation(self, action: ActionRequest) -> bool:
        self.prompted_actions.append(action)
        return self.auto_confirm
