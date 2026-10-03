"""First-run onboarding wizard for NOVA.

Guides new users through microphone selection, offline STT model verification/download,
push-to-talk hotkey configuration, and safety confirmation choices.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

from nova.core.settings import SettingsManager

logger = logging.getLogger(__name__)


class _ModelDownloadThread(QThread):
    progress = Signal(int, str)
    finished_ok = Signal()
    failed = Signal(str)

    def __init__(self, model_size: str = "base.en") -> None:
        super().__init__()
        self.model_size = model_size

    def run(self) -> None:
        try:
            from nova.stt import ModelManager

            mgr = ModelManager()
            if mgr.is_model_cached(self.model_size):
                self.progress.emit(100, "Already cached.")
                self.finished_ok.emit()
                return

            self.progress.emit(10, "Downloading Whisper model...")
            mgr.download_model(self.model_size)
            self.progress.emit(100, "Download complete.")
            self.finished_ok.emit()
        except Exception as e:
            logger.exception("Onboarding model download failed")
            self.failed.emit(str(e))


class WelcomePage(QWizardPage):
    """Initial greeting and privacy guarantee."""

    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Welcome to NOVA")
        self.setSubTitle("The private, offline-first voice assistant for your desktop.")

        layout = QVBoxLayout(self)
        intro = QLabel(
            "NOVA gives you voice control over your desktop without compromising your privacy.\n\n"
            "• 100% Offline: Voice recognition and speech synthesis run locally on your CPU.\n"
            "• Zero Telemetry: No audio, transcripts, or keystrokes leave your device.\n"
            "• Safe Control: Strictly allowlisted actions with confirmation prompts for safety.\n\n"
            "This setup wizard will help you configure your audio and initial preferences."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)


class MicTestPage(QWizardPage):
    """Select and verify microphone input."""

    def __init__(self, settings_mgr: SettingsManager) -> None:
        super().__init__()
        self._settings_mgr = settings_mgr
        self.setTitle("Microphone Setup")
        self.setSubTitle("Choose which microphone NOVA will use to listen for voice commands.")

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._mic_combo = QComboBox()
        self._mic_combo.addItem("System Default")

        try:
            from nova.audio import list_input_devices

            for dev in list_input_devices():
                self._mic_combo.addItem(dev.name)
        except Exception:
            pass

        current = self._settings_mgr.settings.audio.input_device
        if current and self._mic_combo.findText(current) != -1:
            self._mic_combo.setCurrentText(current)

        form.addRow("Microphone:", self._mic_combo)
        layout.addLayout(form)

        info = QLabel("You can always change your audio input device later in Settings.")
        info.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(info)

    def validatePage(self) -> bool:
        selected = self._mic_combo.currentText()
        self._settings_mgr.settings.audio.input_device = (
            None if selected == "System Default" else selected
        )
        return True


class ModelDownloadPage(QWizardPage):
    """Verify or download the local Whisper STT model."""

    def __init__(self, settings_mgr: SettingsManager) -> None:
        super().__init__()
        self._settings_mgr = settings_mgr
        self._download_thread: _ModelDownloadThread | None = None
        self._is_ready = False

        self.setTitle("Speech Recognition Model")
        self.setSubTitle("NOVA uses local Whisper AI models running directly on your CPU.")

        layout = QVBoxLayout(self)
        self._status_label = QLabel("Checking model cache...")
        layout.addWidget(self._status_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._download_btn = QPushButton("Download Base Model (~145 MB)")
        self._download_btn.clicked.connect(self._start_download)
        layout.addWidget(self._download_btn)

    def initializePage(self) -> None:
        try:
            from nova.stt import ModelManager

            mgr = ModelManager()
            if mgr.is_model_cached(self._settings_mgr.settings.stt.model_size):
                self._status_label.setText(
                    "✅ Speech model is already downloaded and ready to use."
                )
                self._download_btn.setEnabled(False)
                self._is_ready = True
                self.completeChanged.emit()
                return
        except Exception:
            pass

        self._status_label.setText("The recommended 'base.en' model needs to be downloaded once.")
        self._download_btn.setEnabled(True)
        self._is_ready = False
        self.completeChanged.emit()

    def _start_download(self) -> None:
        self._download_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._status_label.setText("Downloading model from Hugging Face...")

        self._download_thread = _ModelDownloadThread(self._settings_mgr.settings.stt.model_size)
        self._download_thread.progress.connect(self._on_progress)
        self._download_thread.finished_ok.connect(self._on_finished)
        self._download_thread.failed.connect(self._on_failed)
        self._download_thread.start()

    def _on_progress(self, val: int, msg: str) -> None:
        self._progress.setValue(val)
        self._status_label.setText(msg)

    def _on_finished(self) -> None:
        self._status_label.setText("✅ Model downloaded successfully!")
        self._is_ready = True
        self.completeChanged.emit()

    def _on_failed(self, err: str) -> None:
        self._status_label.setText(f"❌ Download failed: {err}. You can retry or continue.")
        self._download_btn.setEnabled(True)
        # Allow user to continue anyway; they can download later in Settings
        self._is_ready = True
        self.completeChanged.emit()

    def isComplete(self) -> bool:
        return self._is_ready


class HotkeySetupPage(QWizardPage):
    """Configure push-to-talk shortcut."""

    def __init__(self, settings_mgr: SettingsManager) -> None:
        super().__init__()
        self._settings_mgr = settings_mgr
        self.setTitle("Push-to-Talk Hotkey")
        self.setSubTitle("Choose the key you will hold down while speaking voice commands.")

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._hotkey_input = QLineEdit(self._settings_mgr.settings.audio.push_to_talk_key)
        self._hotkey_input.setPlaceholderText("e.g. ctrl_r, alt, space")
        form.addRow("Hotkey:", self._hotkey_input)
        layout.addLayout(form)

        hint = QLabel(
            "Default is 'ctrl_r' (Right Control). While held, NOVA records your speech.\n"
            "When released, NOVA immediately executes your command."
        )
        hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(hint)

    def validatePage(self) -> bool:
        key = self._hotkey_input.text().strip() or "ctrl_r"
        self._settings_mgr.settings.audio.push_to_talk_key = key
        return True


class PermissionsPage(QWizardPage):
    """Safety and destructive action policies."""

    def __init__(self, settings_mgr: SettingsManager) -> None:
        super().__init__()
        self._settings_mgr = settings_mgr
        self.setTitle("Safety & Confirmations")
        self.setSubTitle("Protect your system from accidental destructive voice commands.")

        layout = QVBoxLayout(self)

        self._confirm_lock = QCheckBox("Require confirmation before locking computer")
        self._confirm_lock.setChecked(self._settings_mgr.settings.security.confirm_lock)
        layout.addWidget(self._confirm_lock)

        self._confirm_sleep = QCheckBox("Require confirmation before putting system to sleep")
        self._confirm_sleep.setChecked(self._settings_mgr.settings.security.confirm_sleep)
        layout.addWidget(self._confirm_sleep)

        self._confirm_close = QCheckBox("Require confirmation before closing running applications")
        self._confirm_close.setChecked(self._settings_mgr.settings.security.confirm_close_app)
        layout.addWidget(self._confirm_close)

        desc = QLabel(
            "\nBy default, destructive actions ask for a spoken or on-screen confirmation.\n"
            "Critical system processes (explorer, csrss, etc.) are always protected."
        )
        desc.setStyleSheet("color: #10B981; font-size: 11px;")
        layout.addWidget(desc)

    def validatePage(self) -> bool:
        sec = self._settings_mgr.settings.security
        sec.confirm_lock = self._confirm_lock.isChecked()
        sec.confirm_sleep = self._confirm_sleep.isChecked()
        sec.confirm_close_app = self._confirm_close.isChecked()
        return True


class OnboardingWizard(QWizard):
    """Multi-step first-run onboarding setup wizard."""

    def __init__(self, settings_mgr: SettingsManager, parent: Any = None) -> None:
        super().__init__(parent)
        self._settings_mgr = settings_mgr
        self.setWindowTitle("NOVA Setup Wizard")
        self.setMinimumSize(540, 400)

        self.addPage(WelcomePage())
        self.addPage(MicTestPage(self._settings_mgr))
        self.addPage(ModelDownloadPage(self._settings_mgr))
        self.addPage(HotkeySetupPage(self._settings_mgr))
        self.addPage(PermissionsPage(self._settings_mgr))

    def accept(self) -> None:
        self._settings_mgr.settings.general.onboarding_complete = True
        self._settings_mgr.save(self._settings_mgr.settings)
        super().accept()
