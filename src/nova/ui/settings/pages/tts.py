"""TTS settings page — voice selection and speed."""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from nova.core.settings import NovaSettings

_BUILT_IN_VOICES = [
    "en_US-lessac-medium",
    "en_US-amy-medium",
    "en_US-libritts-high",
    "en_GB-alan-medium",
    "en_GB-jenny_dioco-medium",
]


class _TTSTestThread(QThread):
    done = Signal()
    error = Signal(str)

    def __init__(self, text: str, speed: float, voice: str) -> None:
        super().__init__()
        self._text = text
        self._speed = speed
        self._voice = voice

    def run(self) -> None:
        try:
            from nova.audio.player import AudioPlayer
            from nova.tts import PiperEngine

            engine = PiperEngine(default_voice=self._voice)
            audio = engine.synthesize(self._text)
            player = AudioPlayer()
            player.play_wav(audio, blocking=True)
            self.done.emit()
        except Exception as exc:
            self.error.emit(str(exc))


class TTSPage(QWidget):
    """TTS voice and speed settings."""

    def __init__(self, settings: NovaSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._test_thread: _TTSTestThread | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        voice_group = QGroupBox("Voice (Piper neural TTS — runs offline)")
        form = QFormLayout(voice_group)

        self._voice_combo = QComboBox()
        self._voice_combo.addItems(_BUILT_IN_VOICES)
        if self._settings.tts.voice in _BUILT_IN_VOICES:
            self._voice_combo.setCurrentText(self._settings.tts.voice)
        form.addRow("Voice:", self._voice_combo)

        # Speed slider: 0.75x -> 2.0x (stored as float)
        self._speed_slider = QSlider(Qt.Orientation.Horizontal)
        self._speed_slider.setRange(75, 200)  # represents 0.75-2.00
        self._speed_slider.setValue(int(self._settings.tts.speed * 100))
        self._speed_label = QLabel(f"{self._settings.tts.speed:.2f}x")
        self._speed_slider.valueChanged.connect(
            lambda v: self._speed_label.setText(f"{v / 100:.2f}x")
        )
        form.addRow("Speed:", self._speed_slider)
        form.addRow("", self._speed_label)

        self._test_btn = QPushButton("🔊  Test Voice")
        self._test_btn.setToolTip('Synthesizes "Hello, I am NOVA." and plays it back')
        self._test_btn.clicked.connect(self._run_test)
        form.addRow(self._test_btn)

        self._test_status = QLabel("")
        self._test_status.setStyleSheet("font-size: 11px; color: grey;")
        form.addRow(self._test_status)

        layout.addWidget(voice_group)
        layout.addStretch()

    def _run_test(self) -> None:
        if self._test_thread and self._test_thread.isRunning():
            return
        self._test_btn.setEnabled(False)
        self._test_status.setText("Synthesizing…")
        self._test_thread = _TTSTestThread(
            "Hello, I am NOVA, your offline voice assistant.",
            self._speed_slider.value() / 100.0,
            self._voice_combo.currentText(),
        )
        self._test_thread.done.connect(self._on_test_done)
        self._test_thread.error.connect(self._on_test_error)
        self._test_thread.start()

    def _on_test_done(self) -> None:
        self._test_btn.setEnabled(True)
        self._test_status.setText("✅ Playback finished")

    def _on_test_error(self, error: str) -> None:
        self._test_btn.setEnabled(True)
        self._test_status.setText(f"❌ {error}")

    def apply_to(self, settings: NovaSettings) -> None:
        settings.tts.voice = self._voice_combo.currentText()
        settings.tts.speed = self._speed_slider.value() / 100.0
