# Contributing to RepoPilot

Bug reports with minimal examples, reproducible regression tests and clear
onboarding feedback are welcome.

This is a **loopback-only local developer tool**. Imported repository files
are untrusted input. Do **not** execute imported scripts as part of tests.

## Before making changes

1. Check open [issues](https://github.com/harshitethic/RepoPilot/issues);
   for substantial changes, open an issue describing intended behavior.
2. Use a feature branch and keep one PR focused on one observable problem.
3. Reproduce the issue before editing, then add a test that fails before your
   fix and passes after it.
4. Do not add API keys, local imported repositories, credentials, user archives
   or personal data to code, screenshots, issues or logs.

## Set up and verify

Follow the [first-run guide](docs/first-run.md). From the checkout root:

~~~bash
python -m pip install -r backend/requirements-test.txt
PYTHONPATH=backend python -m unittest discover -s backend/tests -v
python -m compileall -q backend
~~~

On Windows PowerShell, set **$env:PYTHONPATH = "backend"** and run the final
two Python commands normally.

For frontend changes:

~~~bash
cd frontend
npm ci
npm test
npm run build
~~~

The optional browser command **npm run test:e2e** requires Playwright Chromium
and its OS dependencies. Independent CI exercises backend tests on three
Python versions, the frontend build and the real-browser test.

## PR checklist

- Explain the exact failure or UX friction and how it was reproduced.
- State observed results and any **skipped or unavailable tests**.
- Document operating-system differences, possible cleanup problems, and
  resource/security limitations.
- Keep tests network-free where possible. Use small disposable ZIP fixtures.
- Do not equate a deterministic model stub with real LLM performance.
- Do not claim passing CodeQL makes untrusted code importing a sandbox.

## Reporting a security issue

Do not post live secrets or exploit code containing private data publicly.
Where GitHub private vulnerability reporting is available, use it; otherwise
open a minimal, non-sensitive issue requesting a secure reporting channel.

## License

Contributions to this project are accepted under the repository's
[MIT License](LICENSE).
