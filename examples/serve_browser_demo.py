"""Isolated real-HTTP browser demo backend, with deterministic fake LLM only.

Runs the genuine FastAPI importer, indexer, search and AI routes on loopback.
The stubbed final LLM call makes slow-response behavior reproducible offline.
This is not a model-quality test or a production API entrypoint.
"""
from pathlib import Path
import tempfile

import uvicorn

import app as api_module
from services import github


def deterministic_ai(prompt: str) -> str:
    if "DELAYED_ALPHA" in prompt:
        return "alpha_private_answer: response from repository A"
    return "Synthetic LLM answer; this is not a real model output"


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="repopilot-browser-fixture-") as directory:
        github.BASE_DIR = Path(directory)
        api_module.chat = deterministic_ai
        uvicorn.run(api_module.app, host="127.0.0.1", port=8000, log_level="warning")
