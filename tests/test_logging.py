"""Unit tests for the rotating file logging subsystem."""

from __future__ import annotations

import logging
from pathlib import Path

from nova.core.logging import get_logger, setup_logging


def test_logging_setup(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    log_file = setup_logging(log_level=logging.DEBUG, log_dir=log_dir, enable_console=False)

    assert log_file.exists()
    logger = get_logger("nova.test")
    test_msg = "Verification log entry: system initialized."
    logger.info(test_msg)

    content = log_file.read_text(encoding="utf-8")
    assert test_msg in content
    assert "[INFO]" in content
