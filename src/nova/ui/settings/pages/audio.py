"""Audio settings page — microphone selection, VAD, wake word."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from nova.core.settings import NovaSettings


def _list_input_devices() -> list[str]:
    """Return available input device names; gracefully returns empty list on headless."""
    try:
        from nova.audio import list_input_devices

        devices = list_input_devices()
        return [d.name for d in devices]
    except Exception:
        return []


class AudioPage(QWidget):
    """Microphone, VAD sensitivity, and wake word settings."""

    def __init__(self, settings: NovaSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # ── Microphone group ──
        mic_group = QGroupBox("Microphone")
        mic_form = QFormLayout(mic_group)

        self._mic_combo = QComboBox()
        self._mic_combo.addItem("System Default")
        devices = _list_input_devices()
        self._mic_combo.addItems(devices)
        current = self._settings.audio.input_device
        if current and current in devices:
            self._mic_combo.setCurrentText(current)
        mic_form.addRow("Input Device:", self._mic_combo)
        layout.addWidget(mic_group)

        # ── VAD group ──
        vad_group = QGroupBox("Voice Activity Detection")
        vad_form = QFormLayout(vad_group)

        self._vad_slider = QSlider(Qt.Orientation.Horizontal)
        self._vad_slider.setRange(0, 100)
        self._vad_slider.setValue(int(self._settings.audio.vad_threshold * 100))
        self._vad_slider.setToolTip(
            "Higher = only loud, clear speech triggers NOVA. "
            "Lower = more sensitive but may false-trigger."
        )
        self._vad_value_label = QLabel(f"{self._settings.audio.vad_threshold:.0%}")
        self._vad_slider.valueChanged.connect(lambda v: self._vad_value_label.setText(f"{v}%"))
        vad_form.addRow("Sensitivity:", self._vad_slider)
        vad_form.addRow("", self._vad_value_label)
        layout.addWidget(vad_group)

        # ── Wake word group ──
        ww_group = QGroupBox("Wake Word")
        ww_form = QFormLayout(ww_group)

        self._wake_word_enable = QCheckBox('Enable "Hey Nova" wake word')
        self._wake_word_enable.setChecked(self._settings.audio.wake_word_enabled)
        self._wake_word_enable.setToolTip(
            "When enabled, NOVA listens continuously for the wake phrase "
            "in addition to the push-to-talk hotkey."
        )
        ww_form.addRow(self._wake_word_enable)

        offline_note = QLabel("🔒 Wake word detection runs 100% offline on-device.")
        offline_note.setStyleSheet("color: #10B981; font-size: 11px;")
        ww_form.addRow(offline_note)
        layout.addWidget(ww_group)

        layout.addStretch()

    def apply_to(self, settings: NovaSettings) -> None:
        """Write widget values back to settings model."""
        selected = self._mic_combo.currentText()
        settings.audio.input_device = None if selected == "System Default" else selected
        settings.audio.vad_threshold = self._vad_slider.value() / 100.0
        settings.audio.wake_word_enabled = self._wake_word_enable.isChecked()
