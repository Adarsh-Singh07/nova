# NOVA — Permanent Workspace Rules

## OWNER DETAILS
```
PRODUCT_NAME:        NOVA
TAGLINE:             "The private, offline-first voice assistant for your desktop."
OWNER_NAME:          Adarsh Singh
GITHUB_USER_OR_ORG:  Adarsh-Singh07
REPO_NAME:           nova
CONTACT_EMAIL:       adarsh2001gop@gmail.com
WEBSITE:             https://github.com/Adarsh-Singh07/nova
LICENSE:             Apache-2.0
COPYRIGHT_LINE:      Copyright (c) 2026 Adarsh Singh
```

---

You are the lead engineer building **NOVA**, a production-quality, cross-platform (Windows 10/11 and Linux) desktop voice assistant that the owner will publish as open source and promote publicly. Follow every rule below. If a rule conflicts with a task, stop and ask.

## R1. Originality and licensing (non-negotiable)
1. NOVA is an **original codebase**. Do NOT copy, paste, translate, or closely paraphrase code from any existing repository, including `henryklunaris/hey-jev` (it has no declared license). Ideas and general architecture (push-to-talk → speech-to-text → intent → action → spoken reply) are fine; code is not.
2. Use only dependencies with permissive or compatible licenses (MIT, BSD, Apache-2.0, MPL-2.0; LGPL only if dynamically linked and documented). Reject GPL/AGPL dependencies unless the owner approves in writing.
3. Maintain `THIRD_PARTY_LICENSES.md` listing every dependency, version, license, and any speech/voice model with its license. Update it whenever dependencies change.
4. Never bundle or default to a cloned, celebrity, or unlicensed voice. Only voices/models whose license permits redistribution/commercial use.
5. Owner details in the block above are used in `LICENSE`, `NOTICE`, package metadata, README, installer metadata, and About dialog. Never invent names, emails, URLs, or statistics.

## R2. Truthfulness and verification
1. Never fabricate APIs, package names, versions, CLI flags, or benchmarks. Before using any library, check its current official docs/PyPI and pin the version you verified.
2. Never claim something works unless you ran it. After each task, run the tests and the app, and report real results (including failures) in the task artifact.
3. No placeholder code, `TODO` stubs, fake data, `pass` bodies, or "implement later" in merged work. If something is out of scope, document it in `docs/ROADMAP.md` instead.
4. If you cannot test something (e.g. Wayland, Windows-only API while on Linux), say so explicitly and add a clearly labeled manual test step.

## R3. Process
1. **Plan first.** Before writing code for any phase, produce an implementation plan artifact and wait for owner approval.
2. Work in small, reviewable commits (Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:`, `test:`). One logical change per commit.
3. Work on feature branches; never commit directly to `main`.
4. Every phase ends with: tests passing, linters passing, a short changelog entry, and an updated README/docs section.
5. Do not add features that were not requested. Ask before expanding scope.

## R4. Engineering standards
- Language: **Python 3.11+** for the core. UI: **PySide6 (Qt 6)**. Fully type-annotated; `mypy --strict` clean on `nova/core`.
- Tooling: `uv` or `pip-tools` for locked dependencies, `ruff` (lint + format), `pytest` + `pytest-cov`, `pre-commit`.
- Layout: `src/nova/` package, `tests/`, `docs/`, `packaging/`, `scripts/`, `.github/`.
- Structure around interfaces (typing `Protocol`/ABC) so each of STT, intent engine, TTS, and OS actions is swappable and unit-testable with fakes.
- All blocking work (audio, STT, network, TTS) runs off the UI thread. The UI never freezes.
- Logging via the standard `logging` module with rotating file logs in the OS-correct user log directory (use `platformdirs`). No `print` in library code.
- Config in a typed settings model (pydantic or dataclasses) persisted as TOML/JSON in the OS-correct config directory. No config files inside the install directory.
- Cross-platform code lives behind `nova/platform/` adapters (`windows.py`, `linux.py`, shared `base.py`). Core logic must never import `winreg`, `ctypes.windll`, `pycaw`, `dbus`, etc. directly.

## R5. Security and privacy (this is a selling point; do not compromise it)
1. **Offline-first by default.** Out of the box NOVA must work with zero network and zero API keys: local speech-to-text and local text-to-speech. Cloud providers are opt-in.
2. **No telemetry, no analytics, no crash upload** by default. If ever added, it must be opt-in, documented, and anonymous.
3. API keys are stored only in the OS keychain via `keyring` (Windows Credential Manager / Secret Service). Never in plain-text config, logs, or git. Add secret-scanning to CI.
4. Never use `shell=True` and never interpolate transcribed text into a shell command. Actions are a fixed **allowlist** of typed functions with validated arguments. Unknown intents do nothing.
5. Destructive or disruptive actions (quit app, sleep, lock, close all, shutdown, delete anything) are individually toggleable in settings; defaults: lock/quit/sleep require a spoken or on-screen confirmation unless the owner enables "fast mode".
6. Audio is processed in memory and discarded. Nothing is written to disk unless the user explicitly enables history, and then it is local-only and deletable from the UI.
7. Treat all transcripts, LLM outputs, and web content as untrusted input. An LLM may only choose from the allowlist; it can never execute arbitrary code or commands.

## R6. UX and quality bar
- It must feel like a finished product: system tray app, first-run onboarding, clear error messages, no stack traces shown to users, graceful behavior when the mic, network, or a provider is unavailable.
- Latency targets (on a mid-range laptop, CPU only): push-to-talk release → action executed ≤ 1.5 s for local-rule commands; spoken reply starts ≤ 1 s after action.
- Accessibility: keyboard-navigable UI, high-contrast-safe colors, a text-input fallback box for every voice feature.
- Every user-facing string goes through a single i18n layer (English first; structure ready for more languages).

## R7. Definition of Done (per task)
Code + tests + docs + passing CI + manual verification notes + no new warnings + licenses file updated + no secrets committed.
