"""Network-free ASGI request-body admission tests (real multipart and streaming)."""
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import httpx

from app import app
from services import github


def example_archive():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as f:
        f.writestr("src/app.py", "def small_import(): return 1\n")
    return buf.getvalue()


def multipart_zip(archive):
    boundary = "bounded-test-upload"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="tiny.zip"\r\n'
        "Content-Type: application/zip\r\n\r\n"
    ).encode() + archive + f"\r\n--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


class RequestBodyLimitTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addAsyncCleanup(self._cleanup)
        self.temp = temp
        self.repos = Path(temp.name) / "repos"
        self.repos.mkdir()
        self.patch_repo = patch.object(github, "BASE_DIR", self.repos)
        self.patch_repo.start()
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://localhost:8000",
        )
        await self.client.__aenter__()

    async def _cleanup(self):
        await self.client.__aexit__(None, None, None)
        self.patch_repo.stop()
        self.temp.cleanup()

    async def test_oversized_declared_length_rejected_without_reading_stream(self):
        read_chunks = []

        async def stream():
            read_chunks.append(True)
            yield b"a"

        response = await self.client.post(
            "/api/upload", content=stream(),
            headers={"content-length": "999999999", "content-type": "application/octet-stream"},
        )
        self.assertEqual(response.status_code, 413, response.text)
        self.assertEqual(read_chunks, [])
        self.assertEqual(github.repository_ids(), [])

    async def test_missing_length_stream_crosses_limit_and_is_rejected(self):
        import request_limits

        data, content_type = multipart_zip(example_archive())
        async def chunks():
            for start in range(0, len(data), 210):
                yield data[start:start + 210]

        with patch.object(request_limits, "MAX_MULTIPART_BODY_BYTES", 180):
            response = await self.client.post(
                "/api/upload", content=chunks(),
                headers={"content-type": content_type},
            )
        self.assertEqual(response.status_code, 413, response.text)
        self.assertEqual(github.repository_ids(), [])

    async def test_spoofed_small_length_still_counts_actual_body(self):
        import request_limits

        data, content_type = multipart_zip(example_archive())
        async def chunks():
            for start in range(0, len(data), 210):
                yield data[start:start + 210]

        with patch.object(request_limits, "MAX_MULTIPART_BODY_BYTES", 180):
            response = await self.client.post(
                "/api/upload", content=chunks(),
                headers={"content-length": "10", "content-type": content_type},
            )
        self.assertEqual(response.status_code, 413, response.text)

    async def test_malformed_and_duplicate_content_lengths_are_rejected(self):
        for value in ("abc", "-1", "7, 8", "9" * 5000):
            with self.subTest(value=value):
                response = await self.client.post(
                    "/api/upload", content=b"",
                    headers={"content-length": value, "content-type": "multipart/form-data"},
                )
                self.assertEqual(response.status_code, 400, response.text)
        response = await self.client.post(
            "/api/upload", content=b"",
            headers=[("content-length", "1"), ("content-length", "2")],
        )
        self.assertEqual(response.status_code, 400, response.text)

    async def test_actual_valid_multipart_zip_success_at_exact_body_limit(self):
        import request_limits
        body, content_type = multipart_zip(example_archive())
        with patch.object(request_limits, "MAX_MULTIPART_BODY_BYTES", len(body)):
            response = await self.client.post(
                "/api/upload", content=body, headers={"content-type": content_type}
            )
        self.assertEqual(response.status_code, 200, response.text)
        repo_id = response.json()["repo_id"]
        self.assertEqual((self.repos / repo_id / "src" / "app.py").read_text(), "def small_import(): return 1\n")

    async def test_chunked_valid_multipart_upload_and_spool_cleanup(self):
        import request_limits
        data, content_type = multipart_zip(example_archive())
        tracked = []
        original = request_limits.tempfile.SpooledTemporaryFile

        def track_spool(*args, **kwargs):
            spool = original(*args, **kwargs)
            tracked.append(spool)
            return spool

        async def chunks():
            for start in range(0, len(data), 35):
                yield data[start:start + 35]

        with patch.object(request_limits, "SPOOL_MEMORY_BYTES", 64), patch.object(
            request_limits.tempfile, "SpooledTemporaryFile", side_effect=track_spool
        ):
            response = await self.client.post(
                "/api/upload", content=chunks(),
                headers={"content-type": content_type},
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(github.repository_ids()), 1)
        self.assertEqual(len(tracked), 1)
        self.assertTrue(tracked[0]._rolled)
        self.assertTrue(tracked[0].closed)

    async def test_rejected_oversized_stream_closes_temporary_spool(self):
        import request_limits
        data, content_type = multipart_zip(example_archive())
        tracked = []
        original = request_limits.tempfile.SpooledTemporaryFile

        def track_spool(*args, **kwargs):
            spool = original(*args, **kwargs)
            tracked.append(spool)
            return spool

        async def chunks():
            for start in range(0, len(data), 35):
                yield data[start:start + 35]

        with patch.object(request_limits, "SPOOL_MEMORY_BYTES", 16), patch.object(
            request_limits, "MAX_MULTIPART_BODY_BYTES", 180
        ), patch.object(
            request_limits.tempfile, "SpooledTemporaryFile", side_effect=track_spool
        ):
            response = await self.client.post(
                "/api/upload", content=chunks(),
                headers={"content-type": content_type},
            )
        self.assertEqual(response.status_code, 413, response.text)
        self.assertEqual(len(tracked), 1)
        self.assertTrue(tracked[0].closed)
        self.assertEqual(github.repository_ids(), [])

    async def test_unrelated_health_routes_work_without_request_bodies(self):
        response = await self.client.get("/api/health")
        self.assertEqual(response.status_code, 200, response.text)

    async def test_large_json_body_rejected_without_parsing(self):
        import request_limits
        with patch.object(request_limits, "MAX_JSON_BODY_BYTES", 100):
            response = await self.client.post(
                "/api/search",
                json={"repo_id": "a" * 12, "query": "hello", "padding": "X" * 400},
            )
        self.assertEqual(response.status_code, 413, response.text)

    async def test_remote_non_loopback_still_denied(self):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=("198.51.100.10", 12345)),
            base_url="http://localhost:8000",
        ) as external:
            response = await external.post(
                "/api/upload", content=b"test",
                headers={"content-length": "999999999"},
            )
        self.assertEqual(response.status_code, 403, response.text)


if __name__ == "__main__":
    unittest.main()
