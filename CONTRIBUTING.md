# Contributing to NOVA

Thank you for your interest in contributing to **NOVA**! We welcome contributions that align with our core values: **offline-first reliability**, **complete user privacy**, and **production-quality engineering**.

## Code of Conduct

All contributors must adhere to our [Code of Conduct](CODE_OF_CONDUCT.md).

## Development Setup

NOVA requires **Python 3.11+** and uses [`uv`](https://github.com/astral-sh/uv) for fast, reproducible dependency management.

### 1. Clone the repository
```bash
git clone https://github.com/Adarsh-Singh07/nova.git
cd nova
```

### 2. Create and activate a virtual environment
```bash
uv venv --python 3.11
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate
```

### 3. Install dependencies
```bash
uv pip install -e ".[dev]"
```

### 4. Install pre-commit hooks
```bash
pre-commit install
```

## Engineering Rules

When contributing code, please follow these principles:

1. **Originality**: NOVA is an original codebase. Do not copy code from unlicensed or copyleft repositories. Use only dependencies with permissive licenses (MIT, BSD, Apache-2.0).
2. **Type Annotations**: All code in `src/nova/` must be fully type-annotated. `mypy --strict` must pass clean on `nova.core`.
3. **No Shell Injection**: Never use `shell=True` or format strings into raw shell commands. Actions must be defined in the typed allowlist.
4. **Offline First**: Core features must function with zero network connection and zero API keys.
5. **UI Thread Safety**: Never perform audio capture, model inference, network requests, or disk I/O on the main Qt GUI thread.
6. **Tests First**: Every new feature or bugfix must be accompanied by comprehensive tests in `tests/`.

## Running Checks Locally

Before submitting a Pull Request, run the local verification suite:

```bash
# Code formatting and linting
ruff check .
ruff format --check .

# Static type checking
mypy

# Test suite and coverage
pytest --cov=src/nova --cov-report=term-missing
```

## Commit Message Guidelines

We use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` A new user-facing capability
- `fix:` A bug fix
- `docs:` Documentation updates
- `chore:` Dependency updates, CI, or tool configs
- `test:` Adding or updating tests
- `refactor:` Code refactoring without behavioral change

## Pull Request Process

1. Fork the repo and create your feature branch: `git checkout -b feat/my-awesome-feature`.
2. Commit your changes in small, logical commits.
3. Ensure all tests and linters pass.
4. Submit a Pull Request targeting the `main` branch.
5. Provide a clear summary of your changes in the PR template.
