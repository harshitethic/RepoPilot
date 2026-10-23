# Independent developer evaluation: RepoPilot

RepoPilot is a **local-only source explorer**. Its ZIP and search workflows do not require Ollama. A controlled browser/test fixture demonstrates an API contract, **not** the quality of a live model answer.

## Clean first run

1. Use [first-run instructions](first-run.md) for Python 3.11–3.13 and Node 20+ on a trusted workstation. On Windows, use ZIP upload: the backend intentionally does not offer the POSIX Git-process supervision there.
2. Run the deterministic real ASGI smoke test from the checkout root after installing the test dependencies:

```bash
python -m pip install -r backend/requirements-test.txt
PYTHONPATH=backend python -m unittest discover -s backend/tests -p test_http_smoke.py -v
```

   Windows PowerShell command syntax is in [first-run instructions](first-run.md). The smoke test does **not** verify external LLM output.
3. Start the local backend/frontend, create a small ZIP containing `src/hello.py`, import it, and verify exact source path/line search without any AI provider.
4. With two disposable ZIP repositories, switch quickly while a request is delayed. Compare against the [real Chromium fixture test](browser-demo.md); note what was fixture-driven.

## Independent adversarial review

- Attempt duplicate ZIP paths, symlink escapes, traversal names, oversized imports and malformed HTTP bodies within test-only data. Follow the [ZIP](zip-ingestion-security.md) and [request-body](request-body-admission.md) threat models.
- On macOS/Linux, review Git clone timeouts, process-tree cleanup and allowed HTTPS hosts ([process limits](git-process-limits.md)).
- Review cancellation, import resource admission, recovery from partial imports and visibility of error messages ([concurrency](concurrent-work-admission.md)).
- Do not expose the development API publicly or upload sensitive code to public issues.

## Report a verified experience

Open an [issue](https://github.com/harshitethic/RepoPilot/issues) with commit SHA, platform, Python/Node versions, ZIP fixture description, expected/actual, screenshots or sanitized logs and explicit statement of whether you tested a real model. Report issues responsibly under [SECURITY.md](../SECURITY.md) when sensitive.

## Ready for another release?

- [ ] Clean macOS/Linux and Windows ZIP-onboarding checks
- [ ] Backend CI, frontend tests and Chromium regression green
- [ ] Build from a clean checkout, no developer-specific fixtures
- [ ] Dependency upgrade compatibility independently verified before merging
- [ ] Release screenshots label mocks and scripted browser fixtures accurately
- [ ] External review/adoption claims cite independent, reproducible records
