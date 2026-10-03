# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Phase 0: Initial repository foundation.
- Full project structure (`src/nova`, `tests`, `docs`, `packaging`, `scripts`, `.github`).
- Verified `pyproject.toml` with strict `ruff`, `mypy`, and `pytest` configurations.
- GitHub Actions CI workflow with multi-platform matrix (`windows-latest`, `ubuntu-latest`) on Python 3.11 and 3.12.
- Secret scanning via Gitleaks in CI.
- Legal documents: Apache-2.0 `LICENSE`, `NOTICE`, `THIRD_PARTY_LICENSES.md`.
- Community files: `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CONTRIBUTING.md`.
