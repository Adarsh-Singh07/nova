"""Unit tests for NovaTrayIcon."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from nova.ui.signals import NovaSignals
from nova.ui.tray import NovaTrayIcon


def test_tray_icon_creation_and_state_updates(qtbot: Any) -> None:
    signals = NovaSignals()
    settings_mock = MagicMock()
    bubble_mock = MagicMock()
    quit_mock = MagicMock()

    tray = NovaTrayIcon(
        signals=signals,
        on_open_settings=settings_mock,
        on_show_bubble=bubble_mock,
        on_quit=quit_mock,
        fast_mode=True,
    )

    # 1. State updates via signal
    signals.state_changed.emit("listening")
    assert tray._current_state == "listening"
    assert "Listening" in tray.toolTip()

    signals.state_changed.emit("speaking")
    assert tray._current_state == "speaking"
    assert "Speaking" in tray.toolTip()

    # 2. Fast mode quit directly invokes on_quit
    tray._handle_quit()
    quit_mock.assert_called_once()
