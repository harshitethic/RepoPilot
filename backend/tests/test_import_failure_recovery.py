"""Real HTTP regressions for post-import failures and event-loop starvation."""
import asyncio
import io
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import httpx

from app import app
from services import github


def fixture_zip():
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("src/main.py", "def safe_function(): return 1\n")
    return payload.getvalue()


class ImportRecoveryHttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addAsyncCleanup(self._clean_temp)
        self.root = Path(self.temp.name) / "repos"
        self.root.mkdir()
        self.patcher = patch.object(github, "BASE_DIR", self.root)
        self.patcher.start()
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://repopilot.test"
        )
        await self.client.__aenter__()

    async def _clean_temp(self):
        await self.client.__aexit__(None, None, None)
        self.patcher.stop()
        self.temp.cleanup()

    async def upload(self):
        return await self.client.post(
            "/api/upload",
            files={"file": ("project.zip", fixture_zip(), "application/zip")},
        )

    async def test_zip_analysis_failure_drops_only_new_import_and_sanitizes_response(self):
        old = self.root / ("a" * 12)
        old.mkdir()
        (old / "do-not-delete.txt").write_text("valuable")
        with tempfile.TemporaryDirectory() as staged, patch(
            "api_upload.tempfile.tempdir", staged
        ), patch("api_upload.analyze", side_effect=RuntimeError(
            "SECRET_ENV=/home/admin/private"
        )), patch("api_upload.logging"):
            response = await self.upload()
            self.assertEqual(list(Path(staged).glob("repopilot-*.zip")), [])
        self.assertEqual(response.status_code, 500, response.text)
        self.assertNotIn("SECRET_ENV", response.text)
        self.assertEqual(github.repository_ids(), ["a" * 12])
        self.assertEqual((old / "do-not-delete.txt").read_text(), "valuable")

    async def test_zip_analysis_value_error_does_not_expose_sensitive_details(self):
        with patch("api_upload.analyze", side_effect=ValueError(
            "SECRET_DATABASE_URL=/private/database"
        )), patch("api_upload.logging"):
            response = await self.upload()
        self.assertEqual(response.status_code, 500, response.text)
        self.assertNotIn("SECRET_DATABASE_URL", response.text)
        self.assertEqual(github.repository_ids(), [])

    async def test_git_analysis_failure_drops_only_new_import(self):
        existing = self.root / ("a" * 12)
        existing.mkdir()
        (existing / "keep.md").write_text("unchanged")

        def local_clone(_):
            dest = self.root / ("b" * 12)
            dest.mkdir()
            (dest / "src.py").write_text("print('example')")
            return dest.name, dest

        with patch("app.clone_repo", side_effect=local_clone), patch(
            "app.analyze", side_effect=RuntimeError("SECRET_TOKEN: private")
        ), patch("app.logger"):
            response = await self.client.post(
                "/api/analyze", json={"url": "https://github.com/demo/project"}
            )
        self.assertEqual(response.status_code, 500, response.text)
        self.assertNotIn("SECRET_TOKEN", response.text)
        self.assertEqual(github.repository_ids(), ["a" * 12])
        self.assertEqual((existing / "keep.md").read_text(), "unchanged")

    async def test_git_analysis_value_error_does_not_leak_or_preserve_new_repo(self):
        def local_clone(_):
            dest = self.root / ("b" * 12)
            dest.mkdir()
            (dest / "src.py").write_text("content")
            return dest.name, dest

        with patch("app.clone_repo", side_effect=local_clone), patch(
            "app.analyze", side_effect=ValueError("PRIVATE_PATH=/home/secrets")
        ), patch("app.logger"):
            response = await self.client.post(
                "/api/analyze", json={"url": "https://github.com/demo/project"}
            )
        self.assertEqual(response.status_code, 500, response.text)
        self.assertNotIn("PRIVATE_PATH", response.text)
        self.assertEqual(github.repository_ids(), [])

    async def test_failed_rollback_does_not_mask_original_error(self):
        with patch("api_upload.analyze", side_effect=RuntimeError("SECRET_MARKER")), patch(
            "api_upload.rollback_import", side_effect=OSError("PRIVATE_PATH")
        ), patch("api_upload.logging"):
            response = await self.upload()
        self.assertEqual(response.status_code, 500, response.text)
        self.assertNotIn("PRIVATE_PATH", response.text)
        self.assertNotIn("SECRET_MARKER", response.text)

    async def test_zip_heavy_sync_work_does_not_starve_health(self):
        entered = threading.Event()
        timestamps = []
        from api_upload import extract_zip as actual_extract

        def slow_extract(path):
            timestamps.append(time.monotonic())
            entered.set()
            time.sleep(1)
            return actual_extract(path)

        with patch("api_upload.extract_zip", side_effect=slow_extract):
            uploading = asyncio.create_task(self.upload())
            self.assertTrue(await asyncio.wait_for(asyncio.to_thread(entered.wait), 4))
            delay_to_event_loop = time.monotonic() - timestamps[0]
            response = await asyncio.wait_for(self.client.get("/api/health"), 1)
            self.assertEqual(response.status_code, 200)
            self.assertLess(
                delay_to_event_loop, 0.7,
                "Synchronous import work blocked FastAPI's event loop",
            )
            upload_response = await uploading
            self.assertEqual(upload_response.status_code, 200, upload_response.text)


class ScopedRollbackTests(unittest.TestCase):
    def test_unrelated_directory_never_deleted_by_rollback(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            github, "BASE_DIR", Path(tmp)
        ):
            keep = Path(tmp) / ("a" * 12)
            fresh = Path(tmp) / ("b" * 12)
            keep.mkdir()
            fresh.mkdir()
            (keep / "keep.txt").write_text("valuable")
            (fresh / "temp.txt").write_text("fresh")
            with self.assertRaises(ValueError):
                github.rollback_import("a" * 12, fresh)
            self.assertEqual((keep / "keep.txt").read_text(), "valuable")
            self.assertTrue(fresh.exists())
            github.rollback_import("b" * 12, fresh)
            self.assertFalse(fresh.exists())
            self.assertTrue(keep.exists())


if __name__ == "__main__":
    unittest.main()
