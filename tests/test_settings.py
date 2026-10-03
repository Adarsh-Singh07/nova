"""Unit tests for typed settings management and TOML persistence."""

from __future__ import annotations

from pathlib import Path

from nova.core.settings import NovaSettings, SettingsManager


def test_default_settings_initialization() -> None:
    settings = NovaSettings()
    assert settings.general.dark_mode is True
    assert settings.general.locale == "en"
    assert settings.security.fast_mode is False
    assert settings.security.confirm_lock is True
    assert settings.audio.wake_word_enabled is True
    assert settings.audio.push_to_talk_key == "ctrl_r"
    assert settings.stt.model_size == "base.en"
    assert settings.tts.voice == "en_US-lessac-medium"


def test_settings_save_and_load(tmp_path: Path) -> None:
    config_file = tmp_path / "test_config.toml"
    manager = SettingsManager(config_path=config_file)

    assert config_file.exists()
    assert manager.settings.general.dark_mode is True

    # Modify and persist
    manager.settings.general.dark_mode = False
    manager.settings.audio.wake_word_enabled = False
    manager.save()

    # Create fresh manager reading from the same file
    manager2 = SettingsManager(config_path=config_file)
    assert manager2.settings.general.dark_mode is False
    assert manager2.settings.audio.wake_word_enabled is False


def test_corrupted_config_fallback(tmp_path: Path) -> None:
    config_file = tmp_path / "corrupted.toml"
    config_file.write_text("this is not valid [[ toml !!", encoding="utf-8")

    manager = SettingsManager(config_path=config_file)
    # Should fall back to default settings gracefully
    assert manager.settings.general.locale == "en"
    assert manager.settings.security.fast_mode is False


def test_settings_update(tmp_path: Path) -> None:
    config_file = tmp_path / "update_test.toml"
    manager = SettingsManager(config_path=config_file)

    updated = manager.update(general={"locale": "es"})
    assert updated.general.locale == "es"
    assert manager.settings.general.locale == "es"
