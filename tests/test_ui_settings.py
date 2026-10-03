"""Unit tests for SettingsWindow and settings pages."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nova.core.settings import SettingsManager
from nova.ui.settings.window import SettingsWindow


def test_settings_window_load_and_save(tmp_path: Path, qtbot: Any) -> None:
    config_file = tmp_path / "config.toml"
    mgr = SettingsManager(config_path=config_file)
    assert mgr.settings.security.fast_mode is False

    win = SettingsWindow(settings_manager=mgr)
    qtbot.addWidget(win)

    # Check page count (General, Audio, STT, TTS, Actions, LLM)
    assert win._stack.count() == 6

    # Switch pages
    win._switch_page(0)  # General
    assert win._stack.currentIndex() == 0

    win._switch_page(4)  # Actions
    assert win._stack.currentIndex() == 4

    win._switch_page(5)  # LLM
    assert win._stack.currentIndex() == 5

    # Mutate field in General page and LLM page
    win._general_page._fast_mode.setChecked(True)
    win._llm_page._provider_combo.setCurrentIndex(win._llm_page._provider_combo.findData("agnes"))
    win._save()

    # Verify settings persisted
    reloaded_mgr = SettingsManager(config_path=config_file)
    assert reloaded_mgr.settings.security.fast_mode is True
    assert reloaded_mgr.settings.llm.provider == "agnes"
