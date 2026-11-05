"""Real ASGI checks for RAG endpoints, isolation, and safe error responses."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from app import app
from services import github


class RagHttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addAsyncCleanup(self.cleanup)
        self.store = Path(self.temp.name) / "repos"
        self.store.mkdir()
        self.repo_id = "a" * 12
        repo = self.store / self.repo_id
        repo.mkdir()
        (repo / "src").mkdir()
        (repo / "src" / "auth.py").write_text(
            "def authorize_user(token):\n    return bool(token)\n", encoding="utf-8"
        )
        self.patcher = patch.object(github, "BASE_DIR", self.store)
        self.patcher.start()
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://127.0.0.1:8000",
        )
        await self.client.__aenter__()

    async def cleanup(self):
        await self.client.__aexit__(None, None, None)
        self.patcher.stop()
        self.temp.cleanup()

    async def test_retrieval_returns_real_citations_and_scores(self):
        result = await self.client.post("/api/rag/retrieve", json={
            "repo_id": self.repo_id,
            "query": "authorize_user",
            "path_prefix": "src",
        })
        self.assertEqual(result.status_code, 200, result.text)
        data = result.json()
        self.assertEqual(data["retriever"], "bm25")
        self.assertGreater(data["count"], 0)
        self.assertEqual(data["results"][0]["citation"], "src/auth.py:L1-L2")

    async def test_no_evidence_does_not_call_model(self):
        with patch("services.rag.answer.chat", side_effect=AssertionError("model called")):
            result = await self.client.post("/api/rag/ask", json={
                "repo_id": self.repo_id, "question": "completely_unknownzzz"
            })
        self.assertEqual(result.status_code, 200, result.text)
        self.assertFalse(result.json()["model_used"])

    async def test_answer_cites_evidence_when_model_available(self):
        with patch("services.rag.answer.chat", return_value="See src/auth.py:L1-L2"):
            result = await self.client.post("/api/rag/ask", json={
                "repo_id": self.repo_id, "question": "authorize_user"
            })
        self.assertEqual(result.status_code, 200, result.text)
        self.assertTrue(result.json()["model_used"])
        self.assertEqual(result.json()["sources"][0]["path"], "src/auth.py")

    async def test_invalid_repository_is_not_exposed(self):
        malformed = await self.client.post("/api/rag/retrieve", json={
            "repo_id": "../../etc", "query": "password"
        })
        self.assertEqual(malformed.status_code, 400)
        missing = await self.client.post("/api/rag/retrieve", json={
            "repo_id": "b" * 12, "query": "password"
        })
        self.assertEqual(missing.status_code, 404)

    async def test_invalid_prefix_and_request_budgets(self):
        malformed = await self.client.post("/api/rag/retrieve", json={
            "repo_id": self.repo_id, "query": "foo", "path_prefix": "../"
        })
        self.assertEqual(malformed.status_code, 400)
        rejected = await self.client.post("/api/rag/retrieve", json={
            "repo_id": self.repo_id, "query": "foo", "limit": 999
        })
        self.assertEqual(rejected.status_code, 422)

    async def test_existing_loopback_boundary_covers_rag(self):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=("192.0.2.10", 4242)),
            base_url="http://repo.invalid",
        ) as remote:
            result = await remote.post("/api/rag/retrieve", json={
                "repo_id": self.repo_id, "query": "authorize_user"
            })
        self.assertEqual(result.status_code, 403)


if __name__ == "__main__":
    unittest.main()
