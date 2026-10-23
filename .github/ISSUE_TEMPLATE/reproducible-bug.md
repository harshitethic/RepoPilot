---
name: Reproducible bug report
about: Report an independently reproducible defect in RepoPilot
title: "bug: "
labels: []
assignees: []
---

## Environment

- OS and version:
- Python, Node and browser versions:
- Git commit or release:

## Minimal steps to reproduce

1.
2.
3.

State whether the failure occurred during ZIP import, HTTPS Git clone, file indexing, search, UI switching, or optional Ollama. Use a synthetic fixture with no private source code.

## Expected behavior

Describe the observable result that should happen.

## Actual behavior

Describe what actually happened. Attach sanitized terminal output/screenshots if necessary.

## Verification

- [ ] I reproduced this myself from a clean checkout or a stated baseline.
- [ ] I used synthetic/non-confidential data and removed secrets from logs.
- [ ] I checked [independent evaluation guidance](../../docs/independent-evaluation.md) and existing issues.

## Additional context and limitations

State anything you did not test. For sensitive security reports, use SECURITY.md instead of publishing exploit details.

> Real experiences are welcome even when critical. Maintainer, AI-generated or fixture-only tests must not be represented as independent validation.
