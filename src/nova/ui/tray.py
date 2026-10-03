"""NOVA system tray icon and context menu."""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QMessageBox, QSystemTrayIcon

from nova.ui.icons import get_icon
from nova.ui.signals import NovaSignals

logger = logging.getLogger(__name__)

_STATE_TOOLTIPS: dict[str, str] = {
    "idle": "NOVA · Idle — press Ctrl+Alt+N to speak",
    "listening": "NOVA · Listening…",
    "transcribing": "NOVA · Transcribing…",
    "thinking": "NOVA · Thinking…",
    "awaiting_confirmation": "NOVA · Awaiting your confirmation…",
    "acting": "NOVA · Executing action…",
    "speaking": "NOVA · Speaking…",
    "error": "NOVA · Error — check logs",
}


class NovaTrayIcon(QSystemTrayIcon):
    """State-aware system tray icon with context menu."""

    def __init__(
        self,
        signals: NovaSignals,
        on_open_settings: Callable[[], None],
        on_show_bubble: Callable[[], None],
        on_quit: Callable[[], None],
        fast_mode: bool = False,
    ) -> None:
        super().__init__(get_icon("idle"))
        self._signals = signals
        self._on_open_settings = on_open_settings
        self._on_show_bubble = on_show_bubble
        self._on_quit = on_quit
        self._fast_mode = fast_mode
        self._current_state = "idle"

        self._build_menu()
        self._connect_signals()
        self.setToolTip(_STATE_TOOLTIPS["idle"])
        self.show()

    # ─── Menu construction ───────────────────────────────────────────────────

    def _build_menu(self) -> None:
        menu = QMenu()

        # Status label (non-clickable informational header)
        self._status_action = QAction("NOVA · Idle", menu)
        self._status_action.setEnabled(False)
        menu.addAction(self._status_action)
        menu.addSeparator()

        # Settings
        settings_action = QAction("⚙  Open Settings…", menu)
        settings_action.triggered.connect(self._on_open_settings)
        settings_action.setShortcut("Ctrl+,")
        menu.addAction(settings_action)

        # Show bubble / transcript
        bubble_action = QAction("💬  Show Transcript", menu)
        bubble_action.triggered.connect(self._on_show_bubble)
        menu.addAction(bubble_action)

        menu.addSeparator()

        # About / Help
        about_action = QAction("About NOVA", menu)
        about_action.triggered.connect(self._show_about)
        menu.addAction(about_action)

        github_action = QAction("🔗  GitHub / Releases", menu)
        github_action.triggered.connect(self._open_github)
        menu.addAction(github_action)

        menu.addSeparator()

        # Quit
        quit_action = QAction("✕  Quit NOVA", menu)
        quit_action.triggered.connect(self._handle_quit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)

    # ─── Signal wiring ───────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self._signals.state_changed.connect(self._on_state_changed)

    # ─── Slots ───────────────────────────────────────────────────────────────

    def _on_state_changed(self, state: str) -> None:
        self._current_state = state
        self.setIcon(get_icon(state))
        tooltip = _STATE_TOOLTIPS.get(state, f"NOVA · {state}")
        self.setToolTip(tooltip)
        self._status_action.setText(f"NOVA · {state.replace('_', ' ').title()}")

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._on_show_bubble()

    def _handle_quit(self) -> None:
        if self._fast_mode:
            self._on_quit()
            return
        reply = QMessageBox.question(
            None,
            "Quit NOVA",
            "Are you sure you want to quit NOVA?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._on_quit()

    def _show_about(self) -> None:
        QMessageBox.about(
            None,
            "About NOVA",
            "<b>NOVA</b> — The private, offline-first voice assistant for your desktop.<br><br>"
            "Version: 0.1.0<br>"
            "Author: Adarsh Singh<br>"
            "License: Apache-2.0<br><br>"
            '<a href="https://github.com/Adarsh-Singh07/nova">github.com/Adarsh-Singh07/nova</a>',
        )

    def _open_github(self) -> None:
        import webbrowser

        webbrowser.open("https://github.com/Adarsh-Singh07/nova/releases")
