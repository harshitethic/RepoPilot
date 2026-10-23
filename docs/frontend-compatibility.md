# Coordinated React 19 and Vite 8 frontend migration

**Scope:** React and React DOM upgraded together to matching 19.x versions; Vite and its React plugin upgraded together to Vite 8.x / plugin-react 6.x. This resolves the incompatible isolated major-version bumps tracked by [issue #14](https://github.com/harshitethic/RepoPilot/issues/14).

## Versions and runtime

| Package | Previous declared range | New declared range |
| --- | --- | --- |
| React | `^18.3.1` | `^19.3.1` |
| React DOM | `^18.3.1` | `^19.3.1` |
| Vite | `^6.0.5` | `^8.3.5` |
| @vitejs/plugin-react | `^4.3.4` | `^6.1.2` |

The checked lockfile resolves React/React DOM **19.3.1**, Vite **8.3.5** and plugin-react **6.1.2**. Both Vite 8 and plugin-react 6 advertise a Node engine of `^20.19.0 || >=22.12.0`. Node 20.0–20.18, Node 21 and Node 22.0–22.11 are **not** supported. Prefer a supported Node LTS release, and use `npm ci` with the committed lockfile; do not use `--force` or `--legacy-peer-deps`.

## Repeat the frontend compatibility checks

From a fresh public checkout:

```bash
cd frontend
node --version
npm ci
npm ls react react-dom vite @vitejs/plugin-react --depth=0
npm test
npm run build
npm audit --audit-level=high
```

To repeat the browser workflow, install the Python backend dependencies from [first-run guidance](first-run.md), then:

```bash
cd frontend
npx playwright install chromium
CI=1 REPOPILOT_PYTHON=python3 npm run test:e2e
```

The real browser test exercises ZIP import and source search through FastAPI and Vite, form input/validation, the architecture endpoint and ignoring delayed AI output after a repo switch. Its AI handler is deliberately stubbed in the Python fixture, **not** a live Ollama or model-quality test. On a Linux host missing Chromium dependencies, run Playwright's documented browser installation with OS dependencies.

## Verification and boundaries

Initial integration checked **23 October 2026** on an authorized Kali workstation with Node **24.19.0**:

- `npm ci` completed without peer-resolution bypasses.
- The 3 frontend unit tests passed, and the Vite 8 production build succeeded.
- The pre-upgrade browser scenario passed against the actual FastAPI/React app with a deterministic AI fixture.
- `npm audit --audit-level=high` and the separate production-only audit returned **0 vulnerabilities** on the resolved graph at test time.

The enlarged E2E scenario and **Node 20/22** compatibility must be evaluated by the pull-request CI; the Kali result does **not** by itself prove those environments. Backend tests and security boundaries are unaffected by this packaging change but remain part of repository CI.

## Additional compatibility regression coverage

The follow-up browser test suite separates two interaction contracts from the
existing multi-repository isolation scenario. One checks that a GitHub URL is
submitted correctly and a simulated HTTP 422 error is shown without leaving
the button disabled. The other uploads a disposable ZIP and checks that the
architecture panel renders the deterministic local API response. These are
**fixture tests**, not proof of a real remote Git clone or live Ollama inference.

CI also runs `npm audit --audit-level=high` on each frontend Node 20/22 job
using the committed lockfile. Audit results reflect published advisories at
the time of each run and are not independent security certification.

## Manual review checklist

- [ ] Run from a truly clean `npm ci`; do not confuse a cached `node_modules` with the lockfile result.
- [ ] On supported Node 20 and Node 22, run unit tests and production build.
- [ ] In a real Chromium browser, verify URL input and empty validation, ZIP import, code search, architecture response, Ask AI, and stale-response isolation. Clearly mark fixture answers as synthetic.
- [ ] Inspect the bundle and browser console for React root, hydration, deprecation or import warnings.
- [ ] Keep backend + CodeQL workflow green before merging.

**No claim:** This upgrade does not change the AI model, make the local development server safe to expose publicly, or demonstrate deployment on an independent user's machine.
