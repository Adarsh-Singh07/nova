# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Phase 5: PySide6 Desktop UI with System Tray and Status Overlay.
  - Persistent system tray application (`NovaTrayIcon`) with dynamic state-aware colored circle icons (grey idle, red listening, amber transcribing, blue thinking, purple acting, green speaking) and native context menu.
  - Floating status and live transcript bubble (`NovaBubble`) anchored to the bottom-left of the screen with smooth slide and fade animations.
  - Accessible text input fallback box integrated into the bubble, ensuring full keyboard-driven operation without voice input (Rule R6).
  - Tabbed settings window (`SettingsWindow`) with dedicated pages for General, Audio, Speech-to-Text, Text-to-Speech, and Action Permissions.
  - Multi-step first-run onboarding setup wizard (`OnboardingWizard`) guiding microphone selection, local model verification/download, hotkey setup, and destructive action confirmation policies.
  - Cross-thread Qt signal bridge (`NovaSignals`) and `PipelineWorker` executing audio recording, STT, intent matching, platform execution, and TTS synthesis off the main UI thread (Rule R4).
  - 120 automated unit and integration tests passing with 81.03% code coverage.
- Phase 4: Cross-Platform Adapters for Windows 10/11 and Linux.
  - Windows platform adapter (`WindowsPlatformAdapter`) implementing master and per-app volume control via `pycaw`, system mute toggling, non-blocking media key events via `SendInput` with fallback to `WM_APPCOMMAND`, system dark/light theme switching with `WM_SETTINGCHANGE` broadcast via `SendMessageTimeoutW`, non-shell application launching via Windows Start Menu `.lnk` parsing and `os.startfile`, workstation locking via `LockWorkStation`, and suspend via `SetSuspendState`.
  - Linux platform adapter (`LinuxPlatformAdapter`) supporting audio engine runtime detection hierarchy (`wpctl` -> `pactl` -> `amixer`), media playback control via `playerctl` and D-Bus MPRIS2, theme switching across GNOME (`gsettings`) and KDE Plasma (`plasma-apply-lookandfeel`), application launching via XDG Desktop Entry specification (`.desktop`) parsing and non-shell `subprocess.Popen`, screen locking via `loginctl lock-session` with D-Bus Screensaver fallback, and sleep via `systemctl suspend`.
  - Process deny-list protection (`is_critical_process`) preventing inadvertent or malicious termination of critical system processes (`explorer.exe`, `csrss.exe`, `systemd`, `dbus`, `nova.exe`, etc.), with graceful `WM_CLOSE`/`SIGTERM` followed by fallback force termination.
  - Universal contract test suite (`tests/test_platform_contract.py`), comprehensive Windows mock tests (`tests/test_platform_windows.py`), Linux mock tests (`tests/test_platform_linux.py`), and empirical Windows 11 hardware verification report (`docs/test_reports/phase4_windows_live_evidence.md`).
  - Added `MEDIA_STOP` and `VOLUME_APP_SET` to pipeline action execution and `nova doctor` platform diagnostic checks.
- Phase 3: Tier 1 Deterministic Intent Engine.
  - Zero-latency (<1ms) regex and pattern-based deterministic intent engine (`Tier1IntentEngine`) parsing 23 distinct OS and utility intents with zero cloud dependency.
  - Conversational chatter rejection, negation filtering ("don't lock the PC"), and non-command idiom disambiguation ("volume of a sphere", "play it by ear").
  - Compound command parser (`split_compound_commands`) with strict two-half validation guarantee (preventing accidental splitting on phrases like "search salt and pepper").
  - RapidFuzz-backed application registry (`AppRegistry`) with fuzzy matching, ambiguity margin thresholding (10-point gap), and user-customizable alias mapping.
  - Colloquial number and duration parsing (`parse_number`, `parse_duration`) handling multi-unit combinations and spoken fractions.
  - Safety gates requiring high confidence (>=0.85) and R5.5 confirmation flow for destructive actions (lock, sleep, close app, quit).
  - Frozen held-out (206 samples) and dev (108 samples) evaluation suites achieving 100.00% accuracy, 0.00% False-Action Rate on non-commands, and 1.00 precision/recall across all intent classes.
- Phase 2: Real Audio capture, STT, and TTS subsystems.
  - Real microphone audio capture via `sounddevice` with device enumeration, automatic fallback, and polyphase software resampling to 16kHz mono.
  - Energy Voice Activity Detection (`EnergyVAD`) with dynamic ambient noise floor tracking and speech utterance segmenter (`VADSegmenter`).
  - Push-to-talk hotkey listener (`HotkeyListener`) supporting non-blocking key state monitoring.
  - Speech-to-Text inference engine (`WhisperEngine`) utilizing `faster-whisper` CTranslate2 INT8 CPU quantization, with automated model download manager (`ModelManager`).
  - Local neural Text-to-Speech synthesis (`PiperEngine`) powered by Piper ONNX Runtime with persistent on-disk WAV caching (`TTSDiskCache`) achieving <14ms repeat response latency.
  - Audio playback engine (`AudioPlayer`) with non-blocking stream delivery and immediate cancellation support.
  - Offline wake word classifier (`WakeWordEngine`) integrating `openWakeWord`.
  - Comprehensive hardware diagnostic suite in `nova doctor` checking microphone/speaker access, STT models, and TTS voice cache.
  - Latency benchmark script (`scripts/benchmark_latency.py`) and performance documentation in `docs/PERFORMANCE.md` verifying ≤1.5s end-to-end target.
- Phase 1: Core pipeline state machine and interfaces with fakes.
  - Finite state machine (`IDLE`, `LISTENING`, `TRANSCRIBING`, `THINKING`, `AWAITING_CONFIRMATION`, `ACTING`, `SPEAKING`, `ERROR`) with thread-safe transition constraints and listener callbacks.
  - Strongly-typed `Protocol` definitions for STT, Intent, TTS, Platform, and Confirmation handlers.
  - Strict security allowlist and parameter validator in `nova.core.actions` blocking arbitrary code execution and shell metacharacter injection.
  - Typed configuration management (`NovaSettings`, `SettingsManager`) with TOML persistence in the OS user directory via `platformdirs`.
  - Rotating file logging (`nova.core.logging`) in the OS user log directory.
  - Test doubles in `nova.core.fakes` supporting zero-dependency unit tests and CLI `--text` headless mode.
  - End-to-end `NovaPipeline` coordinator wired into `nova --text "<command>"`.
  - 45 automated unit and integration tests with >92% test coverage.
- Phase 0: Initial repository foundation.
- Full project structure (`src/nova`, `tests`, `docs`, `packaging`, `scripts`, `.github`).
- Verified `pyproject.toml` with strict `ruff`, `mypy`, and `pytest` configurations.
- GitHub Actions CI workflow with multi-platform matrix (`windows-latest`, `ubuntu-latest`) on Python 3.11 and 3.12.
- Secret scanning via Gitleaks in CI.
- Legal documents: Apache-2.0 `LICENSE`, `NOTICE`, `THIRD_PARTY_LICENSES.md`.
- Community files: `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CONTRIBUTING.md`.
