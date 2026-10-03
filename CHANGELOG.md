# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
