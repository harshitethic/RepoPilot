# Contributing to RepoPilot

Thanks for helping improve RepoPilot.

RepoPilot is intentionally local-first: it clones public repositories, indexes and searches their source, and sends selected context only to a local Ollama model. Contributions should preserve that model and the project's safety boundary.

## Development setup

Follow the main README for the full environment setup. In short, you need:

- Python 3.12
- Node.js 18+
- Git
- Ollama

Create and activate a Python virtual environment, then install the backend dependencies:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r backend/requirements.txt
```

Install frontend dependencies:

```bash
cd frontend
npm ci
```

Run Ollama, the FastAPI backend, and the Vite frontend in separate terminals as described in the README.

## Before opening a pull request

Run the lightweight checks used by the project:

```bash
python -m compileall -q backend
```

```bash
cd frontend
npm ci
npm run build
```

Also exercise the part of the UI or API you changed.

## Contribution guidelines

- Keep pull requests focused on one problem.
- Prefer small, reviewable commits.
- Update documentation when behavior or setup changes.
- Do not add paid API requirements for core functionality.
- Do not execute code from cloned repositories as part of analysis.
- Avoid logging repository contents, prompts, or local paths unless needed for debugging.
- Keep error messages actionable without exposing sensitive local information.
- Preserve support for Windows, macOS, and Linux where practical.

## Pull request checklist

- [ ] The change has a clear purpose.
- [ ] Backend syntax checks pass when backend code changed.
- [ ] The frontend production build passes when frontend code changed.
- [ ] Relevant manual behavior was tested.
- [ ] Documentation was updated if setup or behavior changed.
- [ ] No secrets, local model data, or generated repository clones were committed.

Thanks for making RepoPilot easier to understand, safer to run, and better to maintain.
