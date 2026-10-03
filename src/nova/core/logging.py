"""Standardized logging configuration with rotating files in OS-correct directory.

Complies with Rule R4 (platformdirs user log directory, rotating file logs, no print).
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import platformdirs

APP_NAME = "nova"
APP_AUTHOR = "Adarsh Singh"
DEFAULT_LOG_FORMAT = "%(asctime)s [%(levelname)s] [%(name)s:%(lineno)d] %(message)s"
MAX_LOG_BYTES = 5 * 1024 * 1024  # 5 MB per file
BACKUP_LOG_COUNT = 5


def setup_logging(
    log_level: int = logging.INFO,
    log_dir: Path | None = None,
    enable_console: bool = True,
) -> Path:
    """Initialize root logging with a rotating file handler and optional console handler.

    Args:
        log_level: Logging severity level (e.g. logging.DEBUG, logging.INFO).
        log_dir: Optional custom log directory. Defaults to OS user log dir.
        enable_console: Whether to attach a StreamHandler to stdout/stderr.

    Returns:
        Path to the primary rotating log file.
    """
    if log_dir is None:
        target_dir = Path(platformdirs.user_log_dir(APP_NAME, APP_AUTHOR))
    else:
        target_dir = log_dir

    target_dir.mkdir(parents=True, exist_ok=True)
    log_file = target_dir / "nova.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers to prevent duplicate lines on re-init
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    formatter = logging.Formatter(DEFAULT_LOG_FORMAT)

    # 1. Rotating File Handler
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=MAX_LOG_BYTES,
        backupCount=BACKUP_LOG_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # 2. Console Handler (for CLI / debug runs)
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    logging.getLogger(__name__).debug("Logging initialized at %s (level=%s)", log_file, log_level)
    return log_file


def get_logger(name: str) -> logging.Logger:
    """Convenience getter for a named logger."""
    return logging.getLogger(name)
