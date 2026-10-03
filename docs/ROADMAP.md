# NOVA Project Roadmap

This document outlines the phased engineering milestones from initial repository foundation to the hardened v1.0.0 open-source release.

---

## Phase Progress Matrix

| Phase | Title | Status | Primary Focus |
| :--- | :--- | :--- | :--- |
| **Phase 0** | **Repo Foundation** | ✅ Completed | Scaffolding, verified dependencies, CI matrix, licensing, and linters. |
| **Phase 1** | **Core Pipeline with Fakes** | ✅ Completed | FSM state machine, typed Protocols, fake STT/TTS, settings, and CLI `--text`. |
| **Phase 2** | **Audio + STT + TTS** | ⏳ Queued | Real mic stream via `sounddevice`, Silero VAD, `faster-whisper`, Piper TTS, and `nova doctor`. |
| **Phase 3** | **Intent Engine (Tier 1)** | ⏳ Queued | Deterministic pattern parser, compound commands, numbers, RapidFuzz app matching, 300+ phrase tests. |
| **Phase 4** | **Platform Adapters** | ⏳ Queued | Windows 10/11 & Linux contract implementations (volume, media keys, sleep, lock, theme, apps). |
| **Phase 5** | **UI (PySide6)** | ⏳ Queued | System tray icon with state colors, floating transcript bubble, settings window, onboarding wizard. |
| **Phase 6** | **Optional Tier 2 LLM Tier** | ⏳ Queued | Ollama, Gemini, OpenRouter, Anthropic, OpenAI adapters with strict JSON schema and injection defense. |
| **Phase 7** | **Skills System** | ⏳ Queued | Sandboxed plugin API, permission declarations, install flow, and 3 example skills. |
| **Phase 8** | **Packaging & Release** | ⏳ Queued | Windows Inno Setup installer & portable zip; Linux AppImage & `.deb`; automated release workflow. |
| **Phase 9** | **Docs, Website & Launch Kit** | ⏳ Queued | Comprehensive documentation site, landing page, Show HN, Reddit, and Product Hunt assets. |
| **Phase 10** | **Hardening & v1.0.0** | ⏳ Queued | Security audit (R5), `pip-audit`, intent engine fuzzing, 8h soak test, clean uninstallation audit. |

---

## Out-of-Scope / Future Enhancements (Post-1.0)

Features explicitly deferred from v1.0 to preserve the security boundary and maintain a tight quality bar:

1. **Arbitrary Code Execution**: NOVA will never support unconstrained code generation or raw shell script execution from voice commands.
2. **Always-On Cloud Listening**: Background streaming of audio to third-party cloud servers is permanently out of scope.
3. **Multi-User Voice Biometrics**: Speaker identification and multi-user profile switching will be evaluated in v1.1+.
4. **macOS Adapter**: Native macOS integration (AppleScript / CoreAudio) is deferred until after Windows and Linux stability is established.
