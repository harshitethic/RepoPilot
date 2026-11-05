"""New RAG endpoints share the existing cross-process AI admission pool."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from app import app
from services import github
from work_admission import ROUTES


class RagAdmissionTests(unittest.IsolatedAsyncioTestCase):
    async def test_rag_routes_are_bounded_by_ai_pool(self):
        self.assertEqual(ROUTES[("POST", "/api/rag/ask")], "ai")
        self.assertEqual(ROUTES[("POST", "/api/rag/retrieve")], "ai")

    async def test_unavailable_admission_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / ("a" * 12)
            repo.mkdir()
            (repo / "test.py").write_text("test_token", encoding="utf-8")
            with patch.object(github, "BASE_DIR", root), patch.dict(os.environ, {
                "REPOPILOT_MAX_INFLIGHT_AI": "0"
            }):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="http://127.0.0.1",
                ) as client:
                    response = await client.post("/api/rag/retrieve", json={
                        "repo_id": "a" * 12, "query": "test_token"
                    })
                self.assertEqual(response.status_code, 503)
                self.assertNotIn("REPOPILOT", response.text)


if __name__ == "__main__":
    unittest.main()
