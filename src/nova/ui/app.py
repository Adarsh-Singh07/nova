"""NOVA main UI application controller and event loop bootstrap.

Initializes the QApplication, manages the system tray icon, floating transcript
bubble, settings dialog, first-run onboarding wizard, and push-to-talk hotkey listener.
Runs all pipeline operations (STT, Intent, Platform Action, TTS) on a background
worker thread so the UI thread is never blocked (Rule R4).
"""

from __future__ import annotations

import logging
import queue
import sys
from typing import Any

import numpy as np
from PySide6.QtCore import QObject, QThread
from PySide6.QtWidgets import QApplication

from nova.audio.capture import AudioCapture
from nova.audio.hotkey import HotkeyListener
from nova.audio.player import AudioPlayer
from nova.core.pipeline import NovaPipeline
from nova.core.settings import SettingsManager
from nova.core.state import PipelineState, PipelineStateMachine
from nova.intent import Tier1IntentEngine
from nova.platform import get_platform_adapter
from nova.stt import WhisperEngine
from nova.tts import PiperEngine
from nova.ui.bubble import NovaBubble
from nova.ui.onboarding import OnboardingWizard
from nova.ui.settings import SettingsWindow
from nova.ui.signals import NovaSignals
from nova.ui.theme import apply_platform_theme
from nova.ui.tray import NovaTrayIcon

logger = logging.getLogger(__name__)


class PipelineWorker(QThread):
    """Background worker executing speech-to-text, intent parsing, action execution, and TTS."""

    def __init__(
        self,
        signals: NovaSignals,
        settings_mgr: SettingsManager,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._signals = signals
        self._settings_mgr = settings_mgr
        self._queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._stop_event = False

        self._pipeline: NovaPipeline | None = None
        self._stt: WhisperEngine | None = None
        self._tts: PiperEngine | None = None
        self._player: AudioPlayer | None = None

    def enqueue_audio(self, audio_data: np.ndarray[Any, Any]) -> None:
        self._queue.put(("audio", audio_data))

    def enqueue_text(self, text: str) -> None:
        self._queue.put(("text", text))

    def stop(self) -> None:
        self._stop_event = True
        self._queue.put(("stop", None))

    def _init_pipeline(self) -> None:
        if self._pipeline is not None:
            return

        state_machine = PipelineStateMachine()
        state_machine.add_listener(
            lambda _old, new_state: self._signals.state_changed.emit(new_state.value)
        )

        self._stt = WhisperEngine(model_size=self._settings_mgr.settings.stt.model_size)
        try:
            self._stt.load_model()
        except Exception as e:
            logger.warning("Could not pre-load Whisper model: %s", e)

        self._tts = PiperEngine(default_voice=self._settings_mgr.settings.tts.voice)
        self._player = AudioPlayer()
        platform = get_platform_adapter()

        from nova.llm import CascadeIntentEngine

        tier1 = Tier1IntentEngine(settings=self._settings_mgr.settings)
        intent = CascadeIntentEngine(
            settings=self._settings_mgr.settings.llm,
            tier1_engine=tier1,
        )

        self._pipeline = NovaPipeline(
            state_machine=state_machine,
            stt=self._stt,
            intent_engine=intent,
            tts=self._tts,
            platform=platform,
            settings=self._settings_mgr.settings,
        )

    def run(self) -> None:
        self._init_pipeline()
        while not self._stop_event:
            try:
                item_type, data = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if item_type == "stop" or self._stop_event:
                break

            try:
                if self._pipeline is None:
                    continue

                if item_type == "audio":
                    self._process_audio(data)
                elif item_type == "text":
                    self._process_text(data)
            except Exception as e:
                logger.exception("Error in pipeline worker: %s", e)
                self._signals.error_occurred.emit(str(e))
                self._signals.state_changed.emit(PipelineState.ERROR.value)
            finally:
                self._signals.turn_finished.emit()

    def _process_audio(self, audio_data: np.ndarray[Any, Any]) -> None:
        assert self._pipeline is not None
        if len(audio_data) < 1600:  # Less than 100ms of audio
            self._signals.state_changed.emit(PipelineState.IDLE.value)
            return

        result = self._pipeline.process_audio(audio_data)
        if result.query:
            self._signals.transcript_updated.emit(result.query)
        if result.spoken_feedback:
            self._signals.reply_ready.emit(result.spoken_feedback)

    def _process_text(self, text: str) -> None:
        assert self._pipeline is not None
        self._signals.transcript_updated.emit(text)
        result = self._pipeline.process_text(text)
        if result.spoken_feedback:
            self._signals.reply_ready.emit(result.spoken_feedback)


class NovaApp(QObject):
    """Main application lifecycle and UI coordinator."""

    def __init__(self, qapp: QApplication, settings_mgr: SettingsManager | None = None) -> None:
        super().__init__()
        self.qapp = qapp
        self.settings_mgr = settings_mgr or SettingsManager()
        self.signals = NovaSignals()

        apply_platform_theme(self.qapp)

        # Settings dialog and Onboarding wizard
        self._settings_dialog: SettingsWindow | None = None
        self._onboarding_wizard: OnboardingWizard | None = None

        # Floating status bubble
        self.bubble = NovaBubble(on_text_submit=self._on_text_submitted)

        # System tray icon
        self.tray = NovaTrayIcon(
            signals=self.signals,
            on_open_settings=self.open_settings,
            on_show_bubble=self.bubble.show_bubble,
            on_quit=self.quit,
            fast_mode=self.settings_mgr.settings.security.fast_mode,
        )

        # Audio capture & worker thread
        self.capture = AudioCapture(
            device_name_or_index=self.settings_mgr.settings.audio.input_device
        )
        self.worker = PipelineWorker(self.signals, self.settings_mgr)

        # Hotkey listener
        self.hotkey_listener = HotkeyListener(
            hotkey_name=self.settings_mgr.settings.audio.push_to_talk_key,
            on_press=self._on_hotkey_pressed,
            on_release=self._on_hotkey_released,
        )

        self._wire_signals()

    def _wire_signals(self) -> None:
        self.signals.state_changed.connect(self.bubble.set_state)
        self.signals.transcript_updated.connect(self.bubble.set_transcript)
        self.signals.reply_ready.connect(self.bubble.set_reply)

    def start(self) -> None:
        """Start the background worker thread and hotkey listener."""
        # Check first-run onboarding
        if not self.settings_mgr.settings.general.onboarding_complete:
            self._onboarding_wizard = OnboardingWizard(self.settings_mgr)
            self._onboarding_wizard.show()

        self.worker.start()
        try:
            self.hotkey_listener.start()
        except Exception as e:
            logger.warning("Could not start push-to-talk hotkey listener: %s", e)

        # Show bubble on launch with a helpful status cue
        self.bubble.show_bubble()
        self.bubble.set_state("idle")
        self.bubble.set_reply(
            "NOVA is active in your tray. Press Right Ctrl to speak, or type here."
        )

    def _on_hotkey_pressed(self) -> None:
        """Invoked when user presses push-to-talk key."""
        try:
            self.capture.start()
            self.signals.state_changed.emit(PipelineState.LISTENING.value)
        except Exception as e:
            logger.warning("Failed to start audio capture: %s", e)

    def _on_hotkey_released(self) -> None:
        """Invoked when user releases push-to-talk key."""
        try:
            audio_data = self.capture.stop()
            self.worker.enqueue_audio(audio_data)
        except Exception as e:
            logger.warning("Failed to stop audio capture: %s", e)
            self.signals.state_changed.emit(PipelineState.IDLE.value)

    def _on_text_submitted(self, text: str) -> None:
        """Invoked when user types a command into the bubble fallback box."""
        self.worker.enqueue_text(text)

    def open_settings(self) -> None:
        if self._settings_dialog is None:
            self._settings_dialog = SettingsWindow(self.settings_mgr)
        self._settings_dialog.show()
        self._settings_dialog.activateWindow()

    def quit(self) -> None:
        """Gracefully shut down background listeners and terminate app."""
        self.hotkey_listener.stop()
        self.worker.stop()
        self.worker.wait(2000)
        self.tray.hide()
        self.bubble.close()
        self.qapp.quit()


def run_ui() -> None:
    """Bootstrap and execute the NOVA PySide6 desktop application."""
    existing_app = QApplication.instance()
    app = existing_app if isinstance(existing_app, QApplication) else QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("NOVA")
    app.setApplicationDisplayName("NOVA")

    settings_mgr = SettingsManager()
    nova_app = NovaApp(app, settings_mgr)
    nova_app.start()

    sys.exit(app.exec())
