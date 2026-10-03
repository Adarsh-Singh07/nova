"""Actions settings page — per-action enable/disable and confirmation toggles."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from nova.core.settings import NovaSettings


class ActionsPage(QWidget):
    """Control which action groups are enabled and which require confirmation."""

    def __init__(self, settings: NovaSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        intro = QLabel(
            "Destructive actions require your voice or on-screen confirmation by default. "
            "Disable confirmation only if you trust that NOVA won't mishear a command."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: grey; font-size: 11px;")
        layout.addWidget(intro)

        # ── Destructive actions confirmation group ──
        confirm_group = QGroupBox("Confirmation Required for Destructive Actions")
        confirm_form = QFormLayout(confirm_group)

        self._confirm_lock = QCheckBox("Lock screen / workstation")
        self._confirm_lock.setChecked(self._settings.security.confirm_lock)
        confirm_form.addRow(self._confirm_lock)

        self._confirm_sleep = QCheckBox("Sleep / suspend system")
        self._confirm_sleep.setChecked(self._settings.security.confirm_sleep)
        confirm_form.addRow(self._confirm_sleep)

        self._confirm_close = QCheckBox("Force-close an application")
        self._confirm_close.setChecked(self._settings.security.confirm_close_app)
        confirm_form.addRow(self._confirm_close)

        layout.addWidget(confirm_group)

        # ── Security note ──
        note_group = QGroupBox("Permanent Safety Constraints")
        note_form = QFormLayout(note_group)

        for note in [
            "🔒  Critical system processes (explorer.exe, csrss.exe, etc.) can never be closed.",
            "🔒  Raw shell commands and code execution are permanently blocked.",
            "🔒  Only allowlisted actions can be executed — unknown intents do nothing.",
        ]:
            label = QLabel(note)
            label.setWordWrap(True)
            label.setStyleSheet("color: #10B981; font-size: 11px;")
            note_form.addRow(label)

        layout.addWidget(note_group)
        layout.addStretch()

    def apply_to(self, settings: NovaSettings) -> None:
        settings.security.confirm_lock = self._confirm_lock.isChecked()
        settings.security.confirm_sleep = self._confirm_sleep.isChecked()
        settings.security.confirm_close_app = self._confirm_close.isChecked()
