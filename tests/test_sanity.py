"""Sanity and package structure tests for NOVA."""

from __future__ import annotations

from click.testing import CliRunner

import nova
from nova.app import main


def test_version() -> None:
    """Verify package version is exposed and matches expected value."""
    assert nova.__version__ == "0.1.0"
    assert nova.__author__ == "Adarsh Singh"
    assert nova.__license__ == "Apache-2.0"


def test_cli_version() -> None:
    """Verify CLI --version prints the correct version string."""
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "NOVA version 0.1.0" in result.output


def test_cli_text_mode() -> None:
    """Verify CLI --text option parses and echoes command."""
    runner = CliRunner()
    result = runner.invoke(main, ["--text", "turn volume up"])
    assert result.exit_code == 0
    assert "Executing command: turn volume up" in result.output


def test_cli_default_invocation() -> None:
    """Verify default CLI launch triggers desktop assistant startup message."""
    runner = CliRunner()
    result = runner.invoke(main, [])
    assert result.exit_code == 0
    assert "Starting NOVA desktop assistant" in result.output


def test_cli_doctor() -> None:
    """Verify CLI doctor command executes successfully."""
    runner = CliRunner()
    result = runner.invoke(main, ["doctor"])
    assert result.exit_code == 0
    assert "NOVA Doctor Diagnostic" in result.output


def test_subpackages_importable() -> None:
    """Ensure all core architectural subpackages can be imported."""
    import nova.audio
    import nova.core
    import nova.i18n
    import nova.llm
    import nova.platform
    import nova.security
    import nova.skills
    import nova.stt
    import nova.tts
    import nova.ui

    assert nova.core is not None
    assert nova.audio is not None
    assert nova.stt is not None
    assert nova.tts is not None
    assert nova.llm is not None
    assert nova.platform is not None
    assert nova.skills is not None
    assert nova.ui is not None
    assert nova.security is not None
    assert nova.i18n is not None
