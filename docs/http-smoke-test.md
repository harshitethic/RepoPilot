# Reproducible HTTP-level demonstration

This is **not a mocked UI screenshot**. The tests call the real FastAPI
application through ASGI and exercise the same HTTP routes as the frontend.

## Try the demonstration

From the repository root (Python 3.12 recommended):

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r backend/requirements-test.txt
PYTHONPATH=backend python -m unittest backend.tests.test_http_smoke -v
```

Windows PowerShell: activate `.venv\Scripts\Activate.ps1` and set
`$env:PYTHONPATH="backend"` before running the last command.

## What this verifies

1. Send a real multipart ZIP upload containing a tiny example repository.
2. Parse/extract it, index files and return transparent health signals.
3. Search real source and verify exact file path and line references.
4. List the import, preview cleanup without deleting data, explicitly delete,
   and confirm the subsequent search returns 404.
5. Ask the AI/architecture HTTP routes to build real source context using a
   **deterministic stub** in place of the external Ollama model.
6. Exercise browser CORS preflight validation, invalid ZIP response handling
   and degraded health reporting when the model is unavailable.

The regression suite also checks failure recovery **after** a successful
import but **before** a successful HTTP response. Failed ZIP/Git analysis
must delete only its own newly reserved workspace, preserve older imports,
avoid leaking private exception details, and clear temporary upload files.
The async ZIP endpoint offloads synchronous extraction and analysis to worker
threads. A real ASGI test verifies that a deliberately slow ZIP extraction
does not stall concurrent health requests.

All temporary repositories are created in an isolated test directory and
removed after each test. The demo does **not** clone from GitHub, execute the
imported source code, require a model download, or claim to benchmark an LLM.
Live Ollama answer quality and remote GitHub connectivity need additional
end-to-end verification on a configured machine.

These checks run automatically on every PR and main branch push via
[GitHub Actions](https://github.com/harshitethic/RepoPilot/actions/workflows/ci.yml).
