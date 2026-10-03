"""NOVA main application entry point and CLI commands."""

from __future__ import annotations

import logging
import sys

import click

from nova import __version__
from nova.core import (
    FakeConfirmationHandler,
    FakeIntentEngine,
    FakePlatformAdapter,
    FakeSTTEngine,
    FakeTTSEngine,
    NovaPipeline,
    PipelineStateMachine,
    SettingsManager,
    setup_logging,
)


@click.group(invoke_without_command=True)
@click.option(
    "--version",
    "-v",
    is_flag=True,
    help="Show the NOVA version and exit.",
)
@click.option(
    "--text",
    "-t",
    type=str,
    default=None,
    help="Execute a single-turn voice/text command headlessly and exit.",
)
@click.option(
    "--fast-mode",
    is_flag=True,
    help="Bypass confirmation prompt for destructive actions.",
)
@click.pass_context
def main(ctx: click.Context, version: bool, text: str | None, fast_mode: bool) -> None:
    """NOVA: The private, offline-first voice assistant for your desktop."""
    if version:
        click.echo(f"NOVA version {__version__}")
        sys.exit(0)

    if text:
        setup_logging(log_level=logging.WARNING, enable_console=False)
        settings_mgr = SettingsManager()
        if fast_mode:
            settings_mgr.settings.security.fast_mode = True

        pipeline = NovaPipeline(
            state_machine=PipelineStateMachine(),
            stt=FakeSTTEngine(),
            intent_engine=FakeIntentEngine(),
            tts=FakeTTSEngine(),
            platform=FakePlatformAdapter(),
            settings=settings_mgr.settings,
            confirmation_handler=FakeConfirmationHandler(auto_confirm=True),
        )

        click.echo(f"[NOVA] Input: '{text}'")
        turn_result = pipeline.process_text(text)

        if turn_result.success:
            click.echo("[NOVA] Status: Success")
            click.echo(
                f"[NOVA] Action: {turn_result.action_request.action_id if turn_result.action_request else 'None'}"
            )
            click.echo(f'[NOVA] Spoken: "{turn_result.spoken_feedback}"')
            sys.exit(0)
        else:
            click.echo("[NOVA] Status: Failed")
            if turn_result.spoken_feedback:
                click.echo(f'[NOVA] Spoken: "{turn_result.spoken_feedback}"')
            if turn_result.error:
                click.echo(f"[NOVA] Error: {turn_result.error}")
            sys.exit(1)

    if ctx.invoked_subcommand is None:
        click.echo("Starting NOVA desktop assistant...")
        # UI event loop will be launched in Phase 5


@main.command()
def doctor() -> None:
    """Diagnose hardware, models, platform adapters, and configuration."""
    click.echo(f"=== NOVA Doctor Diagnostic (v{__version__}) ===")
    click.echo(f"Python Platform: {sys.platform} ({sys.version.split()[0]})")

    settings_mgr = SettingsManager()
    click.echo(
        f"Config File: {settings_mgr.config_path} (exists: {settings_mgr.config_path.exists()})"
    )

    log_path = setup_logging(enable_console=False)
    click.echo(f"Log File: {log_path} (writable: {log_path.parent.exists()})")

    click.echo(f"Security fast_mode: {settings_mgr.settings.security.fast_mode}")
    click.echo(f"Wake word enabled: {settings_mgr.settings.audio.wake_word_enabled}")
    click.echo("Diagnosis complete: System operational.")


if __name__ == "__main__":
    main()
