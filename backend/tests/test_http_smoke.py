"""Real ASGI-level smoke tests with temporary data and no paid AI/network calls.

These tests use real multipart parsing, ZIP extraction, indexing, source search,
routing, response serialization and cleanup. Ollama is stubbed intentionally:
this verifies integration wiring, not language model response quality.
"""
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import httpx
from app import app
from services import github


def demonstration_archive() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.md", "# Demonstration project\nUsed for API smoke tests.\n")
        archive.writestr("src/app.py", "def demo_helper():\n    return 'hello from demo'\n")
        archive.writestr(".gitignore", "__pycache__/\n")
    return buffer.getvalue()


class RealApiSmokeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "imports"
        self.root.mkdir()
        self.repo_patch = patch.object(github, "BASE_DIR", self.root)
        self.repo_patch.start()
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://local.test"
        )
        await self.client.__aenter__()

    async def asyncTearDown(self):
        await self.client.__aexit__(None, None, None)
        self.repo_patch.stop()
        self.temp.cleanup()

    async def upload(self):
        return await self.client.post(
            "/api/upload",
            files={"file": ("example.zip", demonstration_archive(), "application/zip")},
        )

    async def test_full_upload_search_inventory_preview_and_delete(self):
        upload = await self.upload()
        self.assertEqual(upload.status_code, 200, upload.text)
        result = upload.json()
        self.assertTrue(result["signals"]["readme"])
        self.assertTrue(result["signals"]["gitignore"])
        self.assertGreaterEqual(result["file_count"], 2)
        repo_id = result["repo_id"]
        self.assertTrue((self.root / repo_id / "src/app.py").is_file())

        response = await self.client.post(
            "/api/search", json={"repo_id": repo_id, "query": "demo_helper"}
        )
        self.assertEqual(response.status_code, 200, response.text)
        found = response.json()["results"]
        self.assertTrue(any(row["path"] == "src/app.py" and row["line"] == 1 for row in found))

        inventory = await self.client.get("/api/repositories")
        self.assertEqual(inventory.status_code, 200)
        self.assertEqual(inventory.json()["count"], 1)
        self.assertEqual(inventory.json()["repositories"][0]["repo_id"], repo_id)

        preview = await self.client.post("/api/repositories/cleanup", json={})
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.json()["deleted"], [])
        self.assertTrue(preview.json()["dry_run"])
        self.assertTrue((self.root / repo_id).exists())

        removed = await self.client.delete(f"/api/repositories/{repo_id}")
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(removed.json(), {"repo_id": repo_id, "deleted": True})
        self.assertFalse((self.root / repo_id).exists())

        missing = await self.client.post(
            "/api/search", json={"repo_id": repo_id, "query": "demo_helper"}
        )
        self.assertEqual(missing.status_code, 404)

    async def test_llm_route_receives_real_source_context_without_network(self):
        upload = await self.upload()
        self.assertEqual(upload.status_code, 200, upload.text)
        repo_id = upload.json()["repo_id"]
        observed_prompts = []

        def local_model_stub(prompt):
            observed_prompts.append(prompt)
            return "Demonstration result: src/app.py defines demo_helper."

        with patch("app.chat", side_effect=local_model_stub):
            answer = await self.client.post(
                "/api/ask",
                json={"repo_id": repo_id, "question": "Explain demo_helper in src/app.py"},
            )
            self.assertEqual(answer.status_code, 200, answer.text)
            self.assertIn("demo_helper", answer.json()["answer"])
            architecture = await self.client.post(
                "/api/architecture", json={"repo_id": repo_id, "question": "Explain layout"}
            )
            self.assertEqual(architecture.status_code, 200)
        self.assertEqual(len(observed_prompts), 2)
        self.assertIn("src/app.py", observed_prompts[0])
        self.assertIn("demo_helper", observed_prompts[0])

    async def test_cors_and_input_validation_on_real_routes(self):
        blocked = await self.client.options(
            "/api/upload",
            headers={
                "Origin": "https://untrusted.example",
                "Access-Control-Request-Method": "POST",
            },
        )
        self.assertNotEqual(
            blocked.headers.get("access-control-allow-origin"),
            "https://untrusted.example",
        )
        allowed = await self.client.options(
            "/api/upload",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.headers.get("access-control-allow-origin"), "http://localhost:5173")

        invalid_zip = await self.client.post(
            "/api/upload", files={"file": ("file.txt", b"not a zip", "text/plain")}
        )
        self.assertEqual(invalid_zip.status_code, 400)
        self.assertEqual(list(self.root.iterdir()), [])

        wrong_age = await self.client.post(
            "/api/repositories/cleanup", json={"max_age_hours": 0}
        )
        self.assertEqual(wrong_age.status_code, 422)

    async def test_ollama_health_outage_reports_degraded_not_500(self):
        with patch("app.available", side_effect=RuntimeError("PRIVATE_DIAGNOSTIC")), patch("app.logger"):
            response = await self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "ollama": {"online": False, "models": []}})
        self.assertNotIn("PRIVATE_DIAGNOSTIC", response.text)


if __name__ == "__main__":
    unittest.main()
