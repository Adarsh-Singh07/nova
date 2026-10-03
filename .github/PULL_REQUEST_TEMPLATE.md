## Summary of Changes

A concise explanation of the changes made in this Pull Request and why they are necessary.

## Related Issue / Phase
Fixes #(issue number) or Part of Phase X

## Checklist

Before submitting, please ensure your PR satisfies the following quality gates:

- [ ] My code strictly adheres to the engineering standards in `GEMINI.md` / `CONTRIBUTING.md`.
- [ ] My code is fully type-annotated; `mypy --strict` passes on `nova.core`.
- [ ] No `shell=True` or unvalidated shell command interpolations are used.
- [ ] No API keys, credentials, or personal telemetry are committed.
- [ ] Unit tests are included and all tests pass (`pytest`).
- [ ] `ruff check .` and `ruff format --check .` report no errors.
- [ ] If new dependencies were added, they have permissive licenses (MIT/BSD/Apache-2.0) and are recorded in `THIRD_PARTY_LICENSES.md`.
- [ ] Documentation has been updated (if applicable).
