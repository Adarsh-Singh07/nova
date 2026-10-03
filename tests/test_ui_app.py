"""Unit tests for NovaApp and PipelineWorker."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
from PySide6.QtWidgets import QApplication

from nova.core.pipeline import PipelineTurnResult
from nova.core.settings import SettingsManager
from nova.ui.app import NovaApp, PipelineWorker
from nova.ui.signals import NovaSignals


def test_pipeline_worker_text_processing(tmp_path: Path, qtbot: Any) -> None:
    config_file = tmp_path / "config.toml"
    mgr = SettingsManager(config_path=config_file)
    signals = NovaSignals()

    worker = PipelineWorker(signals=signals, settings_mgr=mgr)

    mock_pipeline = MagicMock()
    mock_pipeline.process_text.return_value = PipelineTurnResult(
        query="mute",
        action_request=None,
        action_result=None,
        spoken_feedback="Muted.",
        success=True,
    )
    worker._pipeline = mock_pipeline

    with qtbot.waitSignal(signals.reply_ready, timeout=2000) as blocker:
        worker._process_text("mute")
    assert blocker.args == ["Muted."]
    mock_pipeline.process_text.assert_called_once_with("mute")


def test_pipeline_worker_audio_processing(tmp_path: Path, qtbot: Any) -> None:
    config_file = tmp_path / "config.toml"
    mgr = SettingsManager(config_path=config_file)
    signals = NovaSignals()

    worker = PipelineWorker(signals=signals, settings_mgr=mgr)

    mock_pipeline = MagicMock()
    mock_pipeline.process_audio.return_value = PipelineTurnResult(
        query="volume up",
        action_request=None,
        action_result=None,
        spoken_feedback="Volume increased.",
        success=True,
    )
    worker._pipeline = mock_pipeline

    # Short audio (< 1600 samples) returns immediately
    worker._process_audio(np.zeros(500, dtype=np.float32))
    mock_pipeline.process_audio.assert_not_called()

    # Valid audio
    with qtbot.waitSignal(signals.reply_ready, timeout=2000) as blocker:
        worker._process_audio(np.zeros(3200, dtype=np.float32))
    assert blocker.args == ["Volume increased."]
    mock_pipeline.process_audio.assert_called_once()


def test_nova_app_lifecycle_and_hotkey(tmp_path: Path, qtbot: Any) -> None:
    config_file = tmp_path / "config.toml"
    mgr = SettingsManager(config_path=config_file)
    mgr.settings.general.onboarding_complete = True

    app_instance = QApplication.instance()
    assert isinstance(app_instance, QApplication)

    nova_app = NovaApp(qapp=app_instance, settings_mgr=mgr)

    # Test hotkey pressed -> starts capture & emits listening
    with (
        patch.object(nova_app.capture, "start"),
        qtbot.waitSignal(nova_app.signals.state_changed, timeout=1000) as blocker,
    ):
        nova_app._on_hotkey_pressed()
    assert blocker.args == ["listening"]

    # Test hotkey released -> stops capture & enqueues
    with (
        patch.object(nova_app.capture, "stop", return_value=np.zeros(16000, dtype=np.float32)),
        patch.object(nova_app.worker, "enqueue_audio") as mock_enqueue,
    ):
        nova_app._on_hotkey_released()
        mock_enqueue.assert_called_once()

    # Test text fallback submit
    with patch.object(nova_app.worker, "enqueue_text") as mock_enqueue_text:
        nova_app._on_text_submitted("test command")
        mock_enqueue_text.assert_called_once_with("test command")

    # Test open settings
    nova_app.open_settings()
    assert nova_app._settings_dialog is not None
    assert nova_app._settings_dialog.isVisible()
    nova_app._settings_dialog.close()

    # Test quit cleanup
    with (
        patch.object(nova_app.hotkey_listener, "stop"),
        patch.object(nova_app.worker, "stop"),
        patch.object(nova_app.worker, "wait"),
        patch.object(nova_app.qapp, "quit"),
    ):
        nova_app.quit()
