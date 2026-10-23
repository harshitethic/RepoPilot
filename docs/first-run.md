# First run on a trusted local machine

RepoPilot does not require a paid model API or a running Ollama instance to
index ZIP uploads, display file trees or search source.

## Requirements

- Python 3.11–3.13 (3.12 recommended), **Node.js 20.19+ (20.x) or Node.js 22.12+**, npm, and Git. Vite 8 does not support earlier Node 20/22 minor releases or Node 21; see [frontend compatibility](frontend-compatibility.md).
- A free local TCP port 8000 for FastAPI and port 5173 for Vite.
- Disk space for npm/Python dependencies and imported repositories. Default
  persistent logical storage budget is 2 GiB; see [resource limits](import-storage-budget.md).
- On macOS/Linux the backend can clone public GitHub repositories through
  its POSIX Git child-process supervisor. On **Windows, use ZIP upload**;
  the backend deliberately refuses Git clones without Windows equivalent
  process-group supervision.
- Ollama is optional for code search; required for **AI answers**.

## macOS or Linux

Terminal 1, from a new checkout:

~~~bash
git clone https://github.com/harshitethic/RepoPilot.git
cd RepoPilot
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cd backend
python -m uvicorn app:app --host 127.0.0.1 --port 8000
~~~

Terminal 2, from the RepoPilot checkout root:

~~~bash
cd frontend
npm ci
npm run dev
~~~

Open **http://localhost:5173**. Keep both terminals running. The Vite
development proxy forwards API requests to **127.0.0.1:8000**.

## Windows PowerShell

Terminal 1:

~~~powershell
git clone https://github.com/harshitethic/RepoPilot.git
cd RepoPilot
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
cd backend
python -m uvicorn app:app --host 127.0.0.1 --port 8000
~~~

Terminal 2 from the checkout root:

~~~powershell
cd frontend
npm ci
npm run dev
~~~

Open **http://localhost:5173**. Import a small **ZIP**. Do not enable unsafe
Windows Git subprocess fallback just to clone a remote repository.

## First example without Ollama

Create a ZIP with a small **src/hello.py** containing a function called
**hello**. Upload it through the UI, explore the source tree and search for
**hello**. The search results should show the real source path and line.

For a deterministic automated example, use the real FastAPI ASGI app with a
disposable ZIP fixture. It stubs the external model to test the API contract
but **does not test LLM answer quality**.

macOS/Linux, from the checkout root:

~~~bash
python -m pip install -r backend/requirements-test.txt
PYTHONPATH=backend python -m unittest discover -s backend/tests -p test_http_smoke.py -v
~~~

Windows PowerShell, from the checkout root:

~~~powershell
python -m pip install -r backend\requirements-test.txt
$env:PYTHONPATH = "backend"
python -m unittest discover -s backend/tests -p test_http_smoke.py -v
~~~

To run the complete backend test suite, omit the test filename filter. The
[real browser test](browser-demo.md) also requires Playwright Chromium.

## Optional Ollama

Make sure Ollama is running on the same computer and pull the starter model:

~~~bash
ollama pull llama3.2:1b
~~~

Before starting FastAPI, optionally set a different model:

~~~bash
export OLLAMA_MODEL=llama3.2:3b
~~~

Or, in PowerShell:

~~~powershell
$env:OLLAMA_MODEL = "llama3.2:3b"
~~~

The Ollama endpoint defaults to **http://127.0.0.1:11434** and can be changed
by the **OLLAMA_URL** environment variable. If AI is offline, imported code
search still works; the health endpoint reports model availability.

## Troubleshooting

| Problem | Check |
| --- | --- |
| The browser cannot reach FastAPI | Check **http://127.0.0.1:8000/api/health**, then the Vite dev server on port 5173 |
| Ollama reports offline | Confirm its server is running, your configured model is pulled and OLLAMA_URL is correct |
| Git import rejected on Windows | Use ZIP upload; Windows process isolation is not yet supported |
| HTTP 413 on ZIP upload | Check the [multipart body budget](request-body-admission.md) |
| HTTP 503 while importing | A [work-admission slot](concurrent-work-admission.md) is busy |
| Import fails validation | Check the [archive model](zip-ingestion-security.md) or [Git URL model](github-import-security.md) |
| Git clone times out | Review the [supervisor limitations](git-process-limits.md), without disabling safeguards |

For a reproducible issue, share OS, Python/Node versions, expected/actual
behavior and a tiny public synthetic fixture. **Do not attach secrets or
private repository archives.**
