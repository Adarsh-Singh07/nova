"""Unit tests for Speech-to-Text ModelManager and WhisperEngine."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from nova.stt.whisper_engine import (
    ModelDownloadError,
    ModelManager,
    WhisperEngine,
)


def test_model_manager_supported_models(tmp_path: Path) -> None:
    mgr = ModelManager(cache_dir=tmp_path)
    assert "tiny.en" in mgr.SUPPORTED_MODELS
    assert "base.en" in mgr.SUPPORTED_MODELS
    assert "small.en" in mgr.SUPPORTED_MODELS

    # Unsupported model raises ValueError
    with pytest.raises(ValueError, match="Unsupported model"):
        mgr.download_model("invalid_model_xyz")


def test_model_manager_is_cached(tmp_path: Path) -> None:
    mgr = ModelManager(cache_dir=tmp_path)
    assert not mgr.is_model_cached("base.en")

    # Simulate cached model folder with weights
    model_dir = tmp_path / "base.en"
    model_dir.mkdir(parents=True)
    (model_dir / "model.bin").write_text("weights")

    assert mgr.is_model_cached("base.en")
    assert mgr.get_model_path("base.en") == model_dir


def test_model_manager_download_failure(tmp_path: Path) -> None:
    mgr = ModelManager(cache_dir=tmp_path)

    with patch(
        "faster_whisper.utils.download_model", side_effect=RuntimeError("Network disconnected")
    ):
        with pytest.raises(ModelDownloadError) as exc_info:
            mgr.download_model("tiny.en")
        assert "Check your internet connection" in str(exc_info.value)


def test_whisper_engine_transcribe_empty() -> None:
    engine = WhisperEngine()
    empty = np.zeros(0, dtype=np.float32)

    res = engine.transcribe(empty)
    assert res.text == ""
    assert res.duration_seconds == 0.0


def test_whisper_engine_transcribe_mocked() -> None:
    mock_model = MagicMock()
    mock_segment = MagicMock()
    mock_segment.text = "Hello Nova"
    mock_segment.avg_logprob = -0.1

    mock_info = MagicMock()
    mock_info.language = "en"

    mock_model.transcribe.return_value = ([mock_segment], mock_info)

    engine = WhisperEngine()
    engine._model = mock_model
    engine._is_loaded = True

    audio = np.zeros(16000, dtype=np.float32)
    res = engine.transcribe(audio)

    assert res.text == "Hello Nova"
    assert res.language == "en"
    assert res.duration_seconds == 1.0
