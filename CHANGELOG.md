# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
