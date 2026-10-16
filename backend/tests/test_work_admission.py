"""Real ASGI tests for bounded, cross-process expensive-request admission."""
import asyncio
import io
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import httpx

from app import app
from services import github


def fixture_zip():
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("src/main.py", "def example(): return 1\n")
    return data.getvalue()


class WorkAdmissionHttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.root_temp = tempfile.TemporaryDirectory()
        self.addAsyncCleanup(self._cleanup)
        self.root = Path(self.root_temp.name) / "repos"
        self.root.mkdir()
        self.patcher = patch.object(github, "BASE_DIR", self.root)
        self.patcher.start()
        self.config = patch.dict(os.environ, {
            "REPOPILOT_MAX_INFLIGHT_IMPORTS": "1",
            "REPOPILOT_MAX_INFLIGHT_AI": "1",
        })
        self.config.start()
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://localhost:8000",
        )
        await self.client.__aenter__()

    async def _cleanup(self):
        await self.client.__aexit__(None, None, None)
        self.config.stop()
        self.patcher.stop()
        self.root_temp.cleanup()

    async def ask(self):
        return await self.client.post(
            "/api/ask", json={"repo_id": "a" * 12, "question": "Explain this function"}
        )

    async def test_second_ai_rejected_without_blocking_health_and_slot_reusable(self):
        entered, release = threading.Event(), threading.Event()
        def blocking_ai(*_args):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("test timeout")
            return "response from stub"

        with patch("app.ai", side_effect=blocking_ai):
            first = asyncio.create_task(self.ask())
            try:
                self.assertTrue(await asyncio.wait_for(asyncio.to_thread(entered.wait), 3))
                response = await self.ask()
                self.assertEqual(response.status_code, 503, response.text)
                self.assertEqual(response.headers.get("retry-after"), "1")
                self.assertNotIn("lock", response.text.lower())
                health = await self.client.get("/api/health")
                self.assertEqual(health.status_code, 200)
            finally:
                release.set()
            self.assertEqual((await first).status_code, 200)
            again = await self.ask()
            self.assertEqual(again.status_code, 200, again.text)

    async def test_import_slot_admitted_before_stream_is_consumed(self):
        entered, release = threading.Event(), threading.Event()
        def slow_clone(*_args):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("test timeout")
            raise ValueError("synthetic clone failure")

        read = []
        async def upload_stream():
            read.append(True)
            yield b"anything"

        with patch("app.clone_repo", side_effect=slow_clone):
            first = asyncio.create_task(self.client.post(
                "/api/analyze", json={"url": "https://github.com/demo/example"}
            ))
            try:
                self.assertTrue(await asyncio.wait_for(asyncio.to_thread(entered.wait), 3))
                response = await self.client.post(
                    "/api/upload", content=upload_stream(),
                    headers={"content-type": "application/octet-stream"},
                )
                self.assertEqual(response.status_code, 503, response.text)
                self.assertEqual(read, [])
            finally:
                release.set()
            self.assertEqual((await first).status_code, 400)
        upload = await self.client.post(
            "/api/upload",
            files={"file": ("repo.zip", fixture_zip(), "application/zip")},
        )
        self.assertEqual(upload.status_code, 200, upload.text)

    async def test_ai_and_import_pools_are_independent(self):
        entered, release = threading.Event(), threading.Event()
        def slow_ai(*_args):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("test timeout")
            return "stub"
        with patch("app.ai", side_effect=slow_ai):
            first = asyncio.create_task(self.ask())
            try:
                self.assertTrue(await asyncio.wait_for(asyncio.to_thread(entered.wait), 3))
                upload = await self.client.post(
                    "/api/upload",
                    files={"file": ("repo.zip", fixture_zip(), "application/zip")},
                )
                self.assertEqual(upload.status_code, 200, upload.text)
            finally:
                release.set()
            self.assertEqual((await first).status_code, 200)

    async def test_invalid_limit_setting_fails_closed_and_does_not_reflect_value(self):
        for setting in ("0", "-4", "abc", "9999"):
            with self.subTest(setting=setting), patch.dict(os.environ, {
                "REPOPILOT_MAX_INFLIGHT_AI": setting
            }):
                response = await self.ask()
                self.assertEqual(response.status_code, 503, response.text)
                self.assertNotIn(setting, response.text)

    async def test_separate_process_holds_slot_then_releases_it(self):
        import work_admission
        lock_path = work_admission.slot_path("ai", 0)
        script = """
import sys
from filelock import FileLock
lock = FileLock(sys.argv[1], timeout=0)
with lock:
 print('READY', flush=True)
 sys.stdin.readline()
"""
        child = subprocess.Popen(
            [sys.executable, "-c", script, str(lock_path)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True,
        )
        try:
            self.assertEqual(
                (await asyncio.wait_for(asyncio.to_thread(child.stdout.readline), 5)).strip(),
                "READY",
            )
            blocked = await self.ask()
            self.assertEqual(blocked.status_code, 503, blocked.text)
        finally:
            _stdout, stderr = await asyncio.to_thread(
                child.communicate, "\n", timeout=5,
            )
            self.assertEqual(child.returncode, 0, stderr)
        with patch("app.ai", return_value="success"):
            accepted = await self.ask()
        self.assertEqual(accepted.status_code, 200)

    async def test_configurable_two_ai_slots_admit_two_and_reject_third(self):
        both_entered = threading.Event()
        release = threading.Event()
        mutex = threading.Lock()
        count = 0

        def slow_ai(*_args):
            nonlocal count
            with mutex:
                count += 1
                if count == 2:
                    both_entered.set()
            if not release.wait(5):
                raise RuntimeError("test timeout")
            return "stub"

        with patch.dict(os.environ, {"REPOPILOT_MAX_INFLIGHT_AI": "2"}), patch(
            "app.ai", side_effect=slow_ai
        ):
            first = asyncio.create_task(self.ask())
            second = asyncio.create_task(self.ask())
            try:
                self.assertTrue(await asyncio.wait_for(
                    asyncio.to_thread(both_entered.wait), 3
                ))
                third = await self.client.post(
                    "/api/architecture", json={
                        "repo_id": "a" * 12, "question": "Architecture"
                    }
                )
                self.assertEqual(third.status_code, 503)
                self.assertEqual(count, 2)
            finally:
                release.set()
            self.assertEqual((await first).status_code, 200)
            self.assertEqual((await second).status_code, 200)
            self.assertEqual((await self.ask()).status_code, 200)

    async def test_failure_releases_ai_admission_slot(self):
        with patch("app.ai", side_effect=RuntimeError("PRIVATE_ERROR")), patch(
            "app.logger"
        ):
            response = await self.ask()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("PRIVATE_ERROR", response.text)
        with patch("app.ai", return_value="success"):
            again = await self.ask()
        self.assertEqual(again.status_code, 200)

    async def test_remote_clients_still_denied(self):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=("198.51.100.5", 4455)),
            base_url="http://localhost:8000",
        ) as client:
            response = await client.post(
                "/api/ask", json={"repo_id": "a" * 12, "question": "Explain this"}
            )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
