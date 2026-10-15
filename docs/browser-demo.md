# RepoPilot live browser walkthrough — verified local session

![Real RepoPilot browser workflow captured on Kali](RepoPilot-live-verified-walkthrough.gif)

This animated recording consists of **42 frames captured from Chromium**
connected to a **real FastAPI backend and Vite/React frontend** on a Kali
Linux computer. It is not a design mockup. The entire demo uses a
synthetic, six-file fictional catalog ZIP and no personal repositories,
credentials, private messages or paid model APIs.

## What the browser actually did

1. Load the React landing page and retrieve the local backend health status.
2. Upload a ZIP through the real file-input form to POST /api/upload.
3. Index and analyze six text files, yielding the repo overview and health score.
4. Search the real indexed source for search_catalog; show
   src/catalog.py among the returned search results.
5. Browse the six-file tree and return to the repository overview.

The header correctly reflects the *boolean* Ollama availability returned
by GET /api/health after the frontend regression fix. Ollama was running
locally during recording, but **no language-model answers were generated
or represented in this demonstration**.

## Reproduce locally (two terminals)

Use a trusted local computer with Python 3.11+, Node 20+ and Git:

    git clone https://github.com/harshitethic/RepoPilot.git
    cd RepoPilot
    python3 -m venv .venv
    .venv/bin/python -m pip install -r backend/requirements-test.txt

Start the API in the first terminal:

    PYTHONPATH=backend .venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8000

Start the frontend in the second terminal:

    cd frontend
    npm ci
    npm run dev -- --host 127.0.0.1 --port 5173

Generate the **same six-file synthetic input** from the repository root:

    python3 examples/create_demo_zip.py --output /tmp/fictional-catalog.zip

Open http://127.0.0.1:5173/ on the same machine. Upload the ZIP, select
Code Search, search for search_catalog, and open File Tree. The source
fixture and import behavior are also checked by the network-free
backend/tests/test_browser_demo_fixture.py regression.

## Verification and limitations

- The original Kali session passed landing, upload, search, tree and
  overview assertions against the actual localhost API.
- The committed GIF captures the visible UI at the stated steps. It
  is **not** a high-frame-rate video or evidence of production traffic.
- CI runs the generated fixture import/search test, frontend health-contract
  tests, frontend production build and static security checks.
- The demo does not prove GitHub login, remote inference quality, reliable
  multi-tenant operation, model safety or production-readiness.
- RepoPilot is a trusted **local developer tool**. Do not bind its
  unauthenticated backend publicly to the Internet.

See [GitHub clone boundaries](github-import-security.md) and
[ZIP ingestion boundaries](zip-ingestion-security.md).