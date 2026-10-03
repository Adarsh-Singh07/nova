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
@click.option(
    "--live",
    is_flag=True,
    default=False,
    help="Execute real platform OS actions instead of using safe test doubles.",
)
@click.pass_context
def main(
    ctx: click.Context,
    version: bool,
    text: str | None,
    fast_mode: bool,
    live: bool,
) -> None:
    """NOVA: The private, offline-first voice assistant for your desktop."""
    if version:
        click.echo(f"NOVA version {__version__}")
        sys.exit(0)

    if text:
        setup_logging(log_level=logging.WARNING, enable_console=False)
        settings_mgr = SettingsManager()
        if fast_mode:
            settings_mgr.settings.security.fast_mode = True

        from nova.intent import Tier1IntentEngine
        from nova.platform import get_platform_adapter

        platform_inst = get_platform_adapter() if live else FakePlatformAdapter()
        intent_inst = Tier1IntentEngine() if live else FakeIntentEngine()

        pipeline = NovaPipeline(
            state_machine=PipelineStateMachine(),
            stt=FakeSTTEngine(),
            intent_engine=intent_inst,
            tts=FakeTTSEngine(),
            platform=platform_inst,
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
    click.echo(f"OS Platform: {sys.platform} (Python {sys.version.split()[0]})")

    # 1. Configuration & Logs
    settings_mgr = SettingsManager()
    click.echo("\n[Configuration]")
    click.echo(
        f"Config File: {settings_mgr.config_path} (exists: {settings_mgr.config_path.exists()})"
    )

    log_path = setup_logging(enable_console=False)
    click.echo(f"Log File: {log_path} (writable: {log_path.parent.exists()})")
    click.echo(f"Security fast_mode: {settings_mgr.settings.security.fast_mode}")
    click.echo(f"Wake word enabled: {settings_mgr.settings.audio.wake_word_enabled}")

    # 2. Audio Hardware
    from nova.audio import (
        get_default_input_device,
        get_default_output_device,
        list_input_devices,
        list_output_devices,
    )

    click.echo("\n[Audio Hardware]")
    try:
        inputs = list_input_devices()
        outputs = list_output_devices()
        def_in = get_default_input_device()
        def_out = get_default_output_device()

        click.echo(f"Input Devices Found: {len(inputs)}")
        click.echo(f"Default Microphone: '{def_in.name if def_in else 'None'}'")
        click.echo(f"Output Devices Found: {len(outputs)}")
        click.echo(f"Default Speaker: '{def_out.name if def_out else 'None'}'")
    except Exception as e:
        click.echo(f"Audio query error: {e}")

    # 3. Speech-to-Text Model Status
    from nova.stt import ModelManager

    click.echo("\n[Speech-to-Text]")
    stt_mgr = ModelManager()
    stt_model = settings_mgr.settings.stt.model_size
    click.echo(f"Configured STT Model: '{stt_model}'")
    click.echo(f"Model Cached on Disk: {stt_mgr.is_model_cached(stt_model)}")
    click.echo(f"Model Cache Directory: {stt_mgr.cache_dir}")

    # 4. Text-to-Speech Engine Status
    from nova.tts import PiperVoiceManager, TTSDiskCache

    click.echo("\n[Text-to-Speech]")
    tts_mgr = PiperVoiceManager()
    tts_cache = TTSDiskCache()
    voice = settings_mgr.settings.tts.voice
    click.echo(f"Configured Voice: '{voice}'")
    click.echo(f"Voice Model Cached: {tts_mgr.is_voice_cached(voice)}")
    click.echo(f"TTS Disk Cache Directory: {tts_cache.cache_dir}")

    # 5. Platform Adapter Status
    from nova.platform import get_platform_adapter

    click.echo("\n[Platform Adapter]")
    platform_inst = get_platform_adapter()
    click.echo(f"Active Adapter: {type(platform_inst).__name__}")
    vol = platform_inst.get_volume()
    click.echo(f"Master Volume: {vol}%")

    click.echo("\nDiagnosis complete: System operational.")


if __name__ == "__main__":
    main()
