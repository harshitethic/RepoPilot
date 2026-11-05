"""Real import-to-retrieval-to-deletion regression; no network or LLM required."""
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import httpx

from app import app
from services import github


def archive(path: str, source: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.md", "Synthetic repository, not a production model.")
        z.writestr(path, source)
    return output.getvalue()


class RagImportLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addAsyncCleanup(self.cleanup)
        self.store = Path(self.temp.name) / "repos"
        self.store.mkdir()
        self.storage_patch = patch.object(github, "BASE_DIR", self.store)
        self.storage_patch.start()
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://127.0.0.1:8000",
        )
        await self.client.__aenter__()

    async def cleanup(self):
        await self.client.__aexit__(None, None, None)
        self.storage_patch.stop()
        self.temp.cleanup()

    async def import_file(self, name: str, content: str) -> str:
        response = await self.client.post("/api/upload", files={
            "file": ("fixture.zip", archive(name, content), "application/zip"),
        })
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["repo_id"]

    async def test_two_uploaded_repositories_are_isolated_and_deletable(self):
        first = await self.import_file(
            "src/payments.py",
            "def process_refund(transfer_id):\n    return transfer_id\n",
        )
        second = await self.import_file(
            "src/auth.py",
            "def validate_session(session_token):\n    return bool(session_token)\n",
        )
        self.assertNotEqual(first, second)
        result = await self.client.post("/api/rag/retrieve", json={
            "repo_id": first, "query": "process_refund",
        })
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["results"][0]["citation"], "src/payments.py:L1-L2")
        wrong_repo = await self.client.post("/api/rag/retrieve", json={
            "repo_id": second, "query": "process_refund",
        })
        self.assertEqual(wrong_repo.status_code, 200, wrong_repo.text)
        self.assertEqual(wrong_repo.json()["count"], 0)
        deleted = await self.client.delete(f"/api/repositories/{first}")
        self.assertEqual(deleted.status_code, 200)
        missing = await self.client.post("/api/rag/retrieve", json={
            "repo_id": first, "query": "process_refund",
        })
        self.assertEqual(missing.status_code, 404)
        still_present = await self.client.post("/api/rag/retrieve", json={
            "repo_id": second, "query": "validate_session",
        })
        self.assertEqual(still_present.status_code, 200)
        self.assertEqual(still_present.json()["results"][0]["path"], "src/auth.py")

    async def test_unknown_symbol_never_invokes_model(self):
        repo_id = await self.import_file(
            "src/auth.py",
            "def authorize_user(token):\n    return bool(token)\n",
        )
        with patch("services.rag.answer.chat", side_effect=AssertionError("No evidence")):
            reply = await self.client.post("/api/rag/ask", json={
                "repo_id": repo_id,
                "question": "never_seen_unique_token_739",
            })
        self.assertEqual(reply.status_code, 200, reply.text)
        self.assertEqual(reply.json()["sources"], [])
        self.assertFalse(reply.json()["model_used"])


if __name__ == "__main__":
    unittest.main()
