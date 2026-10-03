"""NOVA main application entry point and CLI commands."""

from __future__ import annotations

import sys

import click

from nova import __version__


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
@click.pass_context
def main(ctx: click.Context, version: bool, text: str | None) -> None:
    """NOVA: The private, offline-first voice assistant for your desktop."""
    if version:
        click.echo(f"NOVA version {__version__}")
        sys.exit(0)

    if text:
        click.echo(f"Executing command: {text}")
        # Core pipeline invocation will be wired in Phase 1
        sys.exit(0)

    if ctx.invoked_subcommand is None:
        click.echo("Starting NOVA desktop assistant...")
        # UI event loop will be launched in Phase 5


@main.command()
def doctor() -> None:
    """Diagnose hardware, models, platform adapters, and configuration."""
    click.echo(f"=== NOVA Doctor Diagnostic (v{__version__}) ===")
    click.echo(f"Python Platform: {sys.platform} ({sys.version.split()[0]})")
    click.echo("Diagnosis complete: Repository initialized.")


if __name__ == "__main__":
    main()
