# Third-Party Licenses

NOVA is committed to transparent, permissive, and compliant open-source licensing.
Every dependency, library, and neural model utilized is cataloged below with its version, license, and source.

## Core Runtime Dependencies

| Package | Version | License | Upstream Project / Repository |
| :--- | :--- | :--- | :--- |
| **PySide6** | `6.7.2` | LGPL-3.0 (Dynamically linked wheel) | https://wiki.qt.io/Qt_for_Python |
| **shiboken6** | `6.7.2` | LGPL-3.0 (Dynamically linked wheel) | https://wiki.qt.io/Qt_for_Python |
| **sounddevice** | `0.5.0` | MIT | https://github.com/spatialaudio/python-sounddevice |
| **numpy** | `1.26.4` | BSD-3-Clause | https://numpy.org/ |
| **faster-whisper** | `1.0.3` | MIT | https://github.com/SYSTRAN/faster-whisper |
| **ctranslate2** | `4.4.0` | MIT | https://github.com/OpenNMT/CTranslate2 |
| **openwakeword** | `0.6.0` | Apache-2.0 | https://github.com/dscripka/openWakeWord |
| **piper-tts** | `1.2.0` | MIT | https://github.com/rhasspy/piper |
| **onnxruntime** | `1.18.1` | MIT | https://github.com/microsoft/onnxruntime |
| **pydantic** | `2.8.2` | MIT | https://github.com/pydantic/pydantic |
| **platformdirs** | `4.2.2` | MIT | https://github.com/platformdirs/platformdirs |
| **keyring** | `25.2.1` | MIT | https://github.com/jaraco/keyring |
| **rapidfuzz** | `3.9.6` | MIT | https://github.com/rapidfuzz/RapidFuzz |
| **click** | `8.1.7` | BSD-3-Clause | https://github.com/pallets/click |
| **httpx** | `0.27.0` | BSD-3-Clause | https://github.com/encode/httpx |
| **tomli-w** | `1.0.0` | MIT | https://github.com/hukkin/tomli-w |
| **psutil** | `5.9.0+` | BSD-3-Clause | https://github.com/giampaolo/psutil |
| **pycaw** | `20260927` | MIT | https://github.com/AndreMiras/pycaw |
| **comtypes** | `1.4.17` | MIT | https://github.com/enthought/comtypes |
| **google-genai** | `2.28.0` | Apache-2.0 | https://github.com/googleapis/python-genai |
| **python-dotenv** | `1.2.4` | BSD-3-Clause | https://github.com/theskumar/python-dotenv |

## Neural Models & Checkpoints

| Model Component | Identifier / Checkpoint | License | Source / Upstream Authority |
| :--- | :--- | :--- | :--- |
| **Speech-to-Text** | Whisper `tiny.en`, `base.en`, `small.en` | MIT | OpenAI / Systran (CTranslate2 converted weights) |
| **Wake Word** | "Hey Nova" / custom ONNX | Apache-2.0 | openWakeWord repository & trained ONNX classifiers |
| **Local Text-to-Speech** | `en_US-lessac-medium` | Public Domain / CC0 | Piper Voices / Rhasspy |
| **Local Text-to-Speech** | `en_US-ryan-medium` | MIT | Piper Voices / Rhasspy |

## Development & Test Tools

| Tool | Version | License | Purpose |
| :--- | :--- | :--- | :--- |
| **ruff** | `0.5.5` | MIT / Apache-2.0 | Linting & code formatting |
| **mypy** | `1.11.0` | MIT | Static type checking |
| **pytest** | `8.3.2` | MIT | Unit and integration test runner |
| **pytest-cov** | `5.0.0` | MIT | Test code coverage measurement |
| **pytest-qt** | `4.4.0` | MIT | Qt event-loop integration testing |
| **pytest-mock** | `3.14.0` | MIT | Test mocking utilities |
| **pre-commit** | `3.7.1` | MIT | Pre-commit Git hook enforcement |

---
*This file is continuously maintained in compliance with NOVA Rule R1.*
