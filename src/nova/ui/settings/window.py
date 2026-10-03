"""Settings main window — tabbed QDialog over all 5 settings pages."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from nova.core.settings import NovaSettings, SettingsManager
from nova.ui.settings.pages.actions import ActionsPage
from nova.ui.settings.pages.audio import AudioPage
from nova.ui.settings.pages.general import GeneralPage
from nova.ui.settings.pages.stt import STTPage
from nova.ui.settings.pages.tts import TTSPage
from nova.ui.theme import SETTINGS_STYLESHEET

logger = logging.getLogger(__name__)

_PAGES = [
    ("⚙  General", "general"),
    ("🎙  Audio", "audio"),
    ("💬  Speech-to-Text", "stt"),
    ("🔊  Text-to-Speech", "tts"),
    ("⚡  Actions", "actions"),
]


class SettingsWindow(QDialog):
    """Tabbed settings dialog for NOVA configuration."""

    def __init__(
        self,
        settings_manager: SettingsManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._mgr = settings_manager
        self._settings = settings_manager.settings.model_copy(deep=True)

        self.setWindowTitle("NOVA Settings")
        self.setMinimumSize(620, 460)
        self.setStyleSheet(SETTINGS_STYLESHEET)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        self._build_ui()

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Sidebar navigation ──
        self._nav = QListWidget()
        self._nav.setFixedWidth(150)
        self._nav.setSpacing(2)
        self._nav.setFrameShape(QListWidget.Shape.NoFrame)
        self._nav.setStyleSheet(
            "QListWidget { background: palette(window); border-right: 1px solid palette(mid); }"
            "QListWidget::item { padding: 10px 14px; border-radius: 4px; }"
            "QListWidget::item:selected { background: rgba(99,102,241,0.15); color: #6366F1; font-weight: 600; }"
        )

        for label, _key in _PAGES:
            item = QListWidgetItem(label)
            self._nav.addItem(item)
        self._nav.currentRowChanged.connect(self._switch_page)
        root.addWidget(self._nav)

        # ── Page stack + buttons ──
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)

        self._stack = QStackedWidget()

        # Instantiate all pages
        self._general_page = GeneralPage(self._settings)
        self._audio_page = AudioPage(self._settings)
        self._stt_page = STTPage(self._settings)
        self._tts_page = TTSPage(self._settings)
        self._actions_page = ActionsPage(self._settings)

        for page in [
            self._general_page,
            self._audio_page,
            self._stt_page,
            self._tts_page,
            self._actions_page,
        ]:
            self._stack.addWidget(page)

        right.addWidget(self._stack)

        # ── Button row ──
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(12, 8, 12, 12)

        restore_btn = QPushButton("Restore Defaults")
        restore_btn.setProperty("role", "danger")
        restore_btn.clicked.connect(self._restore_defaults)
        btn_row.addWidget(restore_btn)

        btn_row.addStretch()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        btn_row.addWidget(buttons)

        right.addLayout(btn_row)
        root.addLayout(right)

        # Select first page
        self._nav.setCurrentRow(0)

    def _switch_page(self, index: int) -> None:
        self._stack.setCurrentIndex(index)

    def _save(self) -> None:
        """Collect values from all pages and persist to disk."""
        self._general_page.apply_to(self._settings)
        self._audio_page.apply_to(self._settings)
        self._stt_page.apply_to(self._settings)
        self._tts_page.apply_to(self._settings)
        self._actions_page.apply_to(self._settings)

        # Write live settings object back to manager and persist
        self._mgr._settings = self._settings
        self._mgr.save(self._settings)
        logger.info("Settings saved to disk.")
        self.accept()

    def _restore_defaults(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        reply = QMessageBox.question(
            self,
            "Restore Defaults",
            "Reset all settings to factory defaults?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            default = NovaSettings()
            self._mgr._settings = default
            self._mgr.save(default)
            self.reject()  # Close and let user re-open with defaults applied
