"""Unit tests for OnboardingWizard."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nova.core.settings import SettingsManager
from nova.ui.onboarding.wizard import OnboardingWizard


def test_onboarding_wizard_flow(tmp_path: Path, qtbot: Any) -> None:
    config_file = tmp_path / "config.toml"
    mgr = SettingsManager(config_path=config_file)
    assert mgr.settings.general.onboarding_complete is False

    wizard = OnboardingWizard(settings_mgr=mgr)
    qtbot.addWidget(wizard)

    # Check page count
    assert len(wizard.pageIds()) == 5

    # Accept wizard
    wizard.accept()

    # Verify settings persisted onboarding_complete = True
    reloaded_mgr = SettingsManager(config_path=config_file)
    assert reloaded_mgr.settings.general.onboarding_complete is True
