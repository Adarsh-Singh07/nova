"""General settings page — hotkey, locale, startup behaviour."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from nova.core.settings import NovaSettings


class GeneralPage(QWidget):
    """General preferences: hotkey, locale, startup, fast_mode."""

    def __init__(self, settings: NovaSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # ── Hotkey group ──
        hotkey_group = QGroupBox("Push-to-Talk Hotkey")
        hotkey_form = QFormLayout(hotkey_group)

        self._hotkey_edit = QLineEdit(self._settings.audio.push_to_talk_key)
        self._hotkey_edit.setPlaceholderText("e.g. ctrl_r or ctrl+alt+n")
        self._hotkey_edit.setToolTip(
            "Keyboard shortcut that activates NOVA's microphone while held. "
            "Use key names like ctrl_r, alt, space."
        )
        hotkey_form.addRow("Hotkey:", self._hotkey_edit)
        layout.addWidget(hotkey_group)

        # ── Language group ──
        lang_group = QGroupBox("Language")
        lang_form = QFormLayout(lang_group)

        self._locale_combo = QComboBox()
        self._locale_combo.addItems(["en — English"])
        self._locale_combo.setToolTip(
            "Interface language (more languages coming in future releases)"
        )
        lang_form.addRow("Locale:", self._locale_combo)
        layout.addWidget(lang_group)

        # ── Startup group ──
        startup_group = QGroupBox("Startup")
        startup_form = QFormLayout(startup_group)

        self._start_minimized = QCheckBox("Start minimized to system tray")
        self._start_minimized.setChecked(self._settings.general.start_minimized)
        startup_form.addRow(self._start_minimized)

        self._launch_at_startup = QCheckBox("Launch NOVA automatically when I log in")
        self._launch_at_startup.setChecked(self._settings.general.launch_at_startup)
        if sys.platform != "win32":
            self._launch_at_startup.setEnabled(False)
            self._launch_at_startup.setToolTip("Auto-start on login is currently Windows-only")
        startup_form.addRow(self._launch_at_startup)
        layout.addWidget(startup_group)

        # ── Security group ──
        security_group = QGroupBox("Security")
        security_form = QFormLayout(security_group)

        self._fast_mode = QCheckBox("Fast mode (skip confirmation for destructive actions)")
        self._fast_mode.setChecked(self._settings.security.fast_mode)
        fast_mode_warning = QLabel(
            "⚠ When enabled, commands like 'lock screen' and 'sleep' execute immediately."
        )
        fast_mode_warning.setWordWrap(True)
        fast_mode_warning.setStyleSheet("color: #F59E0B; font-size: 11px;")
        security_form.addRow(self._fast_mode)
        security_form.addRow(fast_mode_warning)
        layout.addWidget(security_group)

        layout.addStretch()

    def apply_to(self, settings: NovaSettings) -> None:
        """Write current widget values back to the settings model."""
        settings.audio.push_to_talk_key = self._hotkey_edit.text().strip() or "ctrl_r"
        settings.general.start_minimized = self._start_minimized.isChecked()
        settings.general.launch_at_startup = self._launch_at_startup.isChecked()
        settings.security.fast_mode = self._fast_mode.isChecked()
