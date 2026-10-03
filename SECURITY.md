# Security Policy

NOVA is designed from the ground up as a **private, offline-first voice assistant**. Security, local isolation, and confidentiality are foundational promises of this project.

## Supported Versions

Only the latest release of NOVA receives active security updates and vulnerability patches.

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

## Core Security & Privacy Commitments

1. **Offline by Default**: Zero voice data, transcripts, or telemetry leave your machine out of the box. Cloud providers are opt-in only.
2. **Key Protection**: Third-party API keys (e.g. Gemini, OpenAI, Anthropic, OpenRouter) are strictly stored in your operating system's native encrypted keychain via `keyring` (Windows Credential Manager / Secret Service). They are never written to plaintext configuration files or logs.
3. **Allowlist Execution**: NOVA does not execute raw shell commands (`shell=True` is prohibited). All actions must map to verified, type-safe functions with validated arguments.
4. **Untrusted Input Sanitation**: Transcripts and LLM responses are treated as untrusted data. Prompt injection attempts cannot bypass allowlisted action validation.
5. **No Telemetry**: No background usage metrics, analytics, or crash logs are transmitted.

## Reporting a Vulnerability

If you discover a potential security vulnerability in NOVA, **please do not disclose it publicly** in a GitHub issue, discussion, or social media.

Instead, please report security vulnerabilities directly to the maintainer:

* **Email:** adarsh2001gop@gmail.com
* **Subject line:** `[SECURITY] Potential vulnerability in NOVA`

### What to include in your report:
- A clear description of the vulnerability.
- Proof-of-concept steps or code to reproduce the issue.
- Operating system, Python version, and NOVA version.
- Any potential impact or attack vectors you have identified.

### Response timeline:
- **Acknowledgement:** Within 48 hours of receipt.
- **Assessment & Triage:** Within 5 business days.
- **Fix & Advisory:** A coordinated security release will be published with attribution (unless the reporter prefers anonymity).
