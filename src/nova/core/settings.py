"""Typed configuration models and TOML persistence for NOVA.

Complies with Rule R4 (persisted in OS-correct user config directory via platformdirs)
and Rule R5 (secure defaults, confirmations enabled by default).
"""

from __future__ import annotations

import logging
import tomllib
from pathlib import Path
from typing import Any

import platformdirs
import tomli_w
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

APP_NAME = "nova"
APP_AUTHOR = "Adarsh Singh"


class AudioSettings(BaseModel):
    """Audio capture, VAD, and hotkey settings."""

    input_device: str | None = Field(default=None, description="Microphone device name or index.")
    output_device: str | None = Field(
        default=None, description="Speaker output device name or index."
    )
    sample_rate: int = Field(
        default=16000, ge=8000, le=48000, description="Internal audio sample rate in Hz."
    )
    vad_threshold: float = Field(
        default=0.5, ge=0.0, le=1.0, description="VAD voice detection sensitivity."
    )
    push_to_talk_key: str = Field(default="ctrl_r", description="Default push-to-talk hotkey.")
    wake_word_enabled: bool = Field(
        default=True, description="Enable offline 'Hey Nova' wake word."
    )
    wake_word_phrase: str = Field(default="Hey Nova", description="Wake word phrase.")


class STTSettings(BaseModel):
    """Speech-to-Text inference parameters."""

    model_size: str = Field(
        default="base.en", description="faster-whisper model size (tiny.en, base.en, small.en)."
    )
    compute_type: str = Field(
        default="int8", description="CTranslate2 quantization (int8, float16, float32)."
    )
    device: str = Field(default="cpu", description="Compute device (cpu, cuda).")


class TTSSettings(BaseModel):
    """Text-to-Speech synthesis parameters."""

    voice: str = Field(default="en_US-lessac-medium", description="Piper neural voice model name.")
    speed: float = Field(default=1.0, ge=0.5, le=2.0, description="Speech rate multiplier.")
    cache_enabled: bool = Field(
        default=True, description="Cache common synthesized WAV phrases on disk."
    )


class SecuritySettings(BaseModel):
    """Security, allowlists, and confirmation policies (Rule R5)."""

    fast_mode: bool = Field(
        default=False,
        description="If True, bypasses spoken/visual confirmations for destructive actions.",
    )
    confirm_lock: bool = Field(
        default=True, description="Require confirmation before locking workstation."
    )
    confirm_sleep: bool = Field(
        default=True, description="Require confirmation before putting system to sleep."
    )
    confirm_close_app: bool = Field(
        default=True, description="Require confirmation before force closing an app."
    )
    allowlist_strict: bool = Field(
        default=True, description="Block any non-allowlisted action execution."
    )


class LLMSettings(BaseModel):
    """Optional Tier 2 Cloud / Local LLM provider settings (Opt-in)."""

    provider: str = Field(
        default="offline",
        description="Active LLM provider: offline, gemini, ollama, openrouter, openai, anthropic.",
    )
    gemini_model: str = Field(default="gemini-2.0-flash", description="Gemini model identifier.")
    ollama_model: str = Field(default="llama3:8b", description="Local Ollama model name.")
    timeout_seconds: float = Field(
        default=10.0, ge=1.0, le=60.0, description="Provider network timeout."
    )


class GeneralSettings(BaseModel):
    """General desktop application preferences."""

    dark_mode: bool = Field(default=True, description="Application theme.")
    locale: str = Field(default="en", description="User interface language code.")
    start_minimized: bool = Field(default=True, description="Start minimized in system tray.")
    launch_at_startup: bool = Field(default=False, description="Launch NOVA on OS boot.")
    onboarding_complete: bool = Field(
        default=False, description="Whether first-run onboarding has been completed."
    )


class AppSettings(BaseModel):
    """Application management and user-configurable alias mappings."""

    aliases: dict[str, str] = Field(
        default_factory=lambda: {
            "code": "Visual Studio Code",
            "vscode": "Visual Studio Code",
            "browser": "Google Chrome",
            "chrome": "Google Chrome",
            "terminal": "Windows Terminal",
            "calculator": "Calculator",
            "calc": "Calculator",
            "spotify": "Spotify",
            "slack": "Slack",
            "notepad": "Notepad",
            "files": "File Explorer",
            "explorer": "File Explorer",
        },
        description="User-customizable mappings from spoken aliases to system application names.",
    )


class NovaSettings(BaseModel):
    """Root configuration model for NOVA."""

    general: GeneralSettings = Field(default_factory=GeneralSettings)
    audio: AudioSettings = Field(default_factory=AudioSettings)
    stt: STTSettings = Field(default_factory=STTSettings)
    tts: TTSSettings = Field(default_factory=TTSSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    apps: AppSettings = Field(default_factory=AppSettings)


class SettingsManager:
    """Manages loading, saving, and persisting settings to OS-correct config directory."""

    def __init__(self, config_path: Path | None = None) -> None:
        if config_path is None:
            config_dir = Path(platformdirs.user_config_dir(APP_NAME, APP_AUTHOR))
            self._config_path = config_dir / "config.toml"
        else:
            self._config_path = config_path

        self._settings = self.load()

    @property
    def config_path(self) -> Path:
        """Return the active configuration file path."""
        return self._config_path

    @property
    def settings(self) -> NovaSettings:
        """Return the in-memory settings instance."""
        return self._settings

    def load(self) -> NovaSettings:
        """Load settings from config.toml, or create defaults if missing."""
        if not self._config_path.exists():
            logger.info("No config file found at %s. Initializing defaults.", self._config_path)
            default_settings = NovaSettings()
            self.save(default_settings)
            return default_settings

        try:
            with open(self._config_path, "rb") as f:
                data = tomllib.load(f)
            loaded = NovaSettings.model_validate(data)
            logger.debug("Successfully loaded configuration from %s", self._config_path)
            return loaded
        except Exception:
            logger.exception(
                "Error parsing configuration at %s. Falling back to defaults.",
                self._config_path,
            )
            return NovaSettings()

    def save(self, settings: NovaSettings | None = None) -> None:
        """Persist settings to config.toml."""
        if settings is not None:
            self._settings = settings

        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        raw_dict: dict[str, Any] = self._settings.model_dump()

        def _prune_none(d: Any) -> Any:
            if isinstance(d, dict):
                return {k: _prune_none(v) for k, v in d.items() if v is not None}
            if isinstance(d, list):
                return [_prune_none(v) for v in d if v is not None]
            return d

        clean_dict = _prune_none(raw_dict)

        try:
            with open(self._config_path, "wb") as f:
                tomli_w.dump(clean_dict, f)
            logger.debug("Saved configuration to %s", self._config_path)
        except Exception:
            logger.exception("Failed to write configuration to %s", self._config_path)
            raise

    def update(self, **kwargs: Any) -> NovaSettings:
        """Update specific settings attributes and persist."""
        data = self._settings.model_dump()
        for key, value in kwargs.items():
            if key in data and isinstance(value, dict):
                data[key].update(value)
            else:
                data[key] = value

        updated = NovaSettings.model_validate(data)
        self.save(updated)
        return updated
