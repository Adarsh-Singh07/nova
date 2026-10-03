<p align="center">
  <h1 align="center">🎙️ NOVA</h1>
  <p align="center"><strong>The private, offline-first voice assistant for your desktop.</strong></p>
</p>

<p align="center">
  <a href="https://github.com/Adarsh-Singh07/nova/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg" alt="License: Apache-2.0"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue.svg" alt="Python 3.11+"></a>
  <a href="#"><img src="https://img.shields.io/badge/Platforms-Windows%20%7C%20Linux-brightgreen.svg" alt="Platforms"></a>
  <a href="https://github.com/Adarsh-Singh07/nova/actions"><img src="https://img.shields.io/github/actions/workflow/status/Adarsh-Singh07/nova/ci.yml?branch=main&label=CI" alt="CI Status"></a>
  <a href="SECURITY.md"><img src="https://img.shields.io/badge/Privacy-100%25%20Offline%20First-green.svg" alt="Privacy First"></a>
</p>

---

## 🌟 What is NOVA?

**NOVA** is a lightweight, modern desktop voice assistant designed for developers, power users, and privacy-conscious individuals. It lives silently in your system tray, listens via push-to-talk (Right Ctrl) or wake-word ("Hey Nova"), executes system tasks on your computer, and replies aloud with low latency.

Unlike conventional voice assistants, NOVA requires **zero cloud connection, zero subscriptions, and zero API keys** to function. Everything runs directly on your local hardware.

---

## ✨ Key Differentiators

- 🔒 **100% Private & Offline by Default**: Local speech-to-text (`faster-whisper`), local neural speech synthesis (`piper-tts`), and local intent processing. No audio or transcript leaves your machine.
- ⚡ **Near-Zero Latency**: Deterministic rule-based intent parsing (Tier 1) resolves commands in under 1.5 seconds on CPU.
- 🤖 **Optional Bring-Your-Own-Key AI (Tier 2)**: Plug in local Ollama, Google Gemini, Anthropic, or OpenAI models for complex conversational inquiries, while always retaining local control.
- 🛡️ **Zero Shell Injection Risk**: Every action is governed by a strict, typed function allowlist. Untrusted transcripts can never execute arbitrary terminal commands.
- 🧩 **Extensible Skills Architecture**: Easily build modular Python or YAML plugins with declarative sandbox permissions.
- 🪟🐧 **True Cross-Platform Symmetry**: Native adapters for Windows 10/11 and Linux (X11 & Wayland).

---

## 🚀 Quick Start (Development)

### Prerequisites
- **Python 3.11+**
- Recommended: [`uv`](https://github.com/astral-sh/uv)

### Installation
```bash
# Clone the repository
git clone https://github.com/Adarsh-Singh07/nova.git
cd nova

# Create virtual environment and install dependencies
uv venv --python 3.11
# Windows:
.venv\Scripts\activate
# Linux:
source .venv/bin/activate

# Install NOVA with development tools
uv pip install -e ".[dev]"
```

### Run NOVA
```bash
# Start NOVA desktop assistant (Tray + Overlay)
nova

# Run headless single-turn text command (ideal for testing)
nova --text "turn volume up"

# Diagnose hardware, models, and platform adapters
nova doctor
```

---

## 🏗️ Architecture at a Glance

```
User Voice / Hotkey
       │
       ▼
[ sounddevice (16kHz PCM) ] ──▶ [ Silero VAD / openWakeWord ]
                                              │
                                              ▼
[ faster-whisper (CTranslate2 INT8) ] ──▶ Transcribed Text
                                              │
                                              ▼
[ Core Intent Engine ] ─────────────────▶ Tier 1: Deterministic Pattern & Slot Parser
  (Optional Tier 2: LLM Fallback)              │
                                              ▼
[ Security Allowlist & Confirmation ] ──▶ Validated ActionRequest
                                              │
                                              ▼
[ Platform Adapters ] ──────────────────▶ Windows (CoreAudio, Win32) / Linux (wpctl, MPRIS)
                                              │
                                              ▼
[ Piper Neural TTS / Audio Playback ] ──▶ Spoken Response
```

---

## 🗺️ Project Roadmap

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the active phased delivery schedule from Phase 0 to Phase 10 (v1.0.0 Release).

---

## 📄 License & Attribution

NOVA is licensed under the [Apache License, Version 2.0](LICENSE).  
Copyright (c) 2026 [Adarsh Singh](https://github.com/Adarsh-Singh07).

For third-party dependencies and model licenses, see [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
