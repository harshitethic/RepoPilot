"""Streamed uploads: size cap, cleanup and predictable error behavior."""
import asyncio
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException, UploadFile
from api_upload import write_temp_upload, upload_repository


class UploadTempFileTests(unittest.TestCase):
    def upload(self, data, filename="repo.zip"):
        return UploadFile(filename=filename, file=io.BytesIO(data))

    def test_unique_temp_files_have_distinct_exact_contents(self):
        first = asyncio.run(write_temp_upload(self.upload(b"first")))
        second = asyncio.run(write_temp_upload(self.upload(b"second")))
        try:
            self.assertNotEqual(first, second)
            self.assertEqual(first.read_bytes(), b"first")
            self.assertEqual(second.read_bytes(), b"second")
        finally:
            first.unlink(missing_ok=True)
            second.unlink(missing_ok=True)

    def test_byte_limit_allows_exact_max_and_rejects_one_over(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("api_upload.MAX_UPLOAD_BYTES", 4), patch(
                "api_upload.UPLOAD_CHUNK_BYTES", 2
            ), patch("api_upload.tempfile.tempdir", tmp):
                accepted = asyncio.run(write_temp_upload(self.upload(b"1234")))
                self.assertEqual(accepted.read_bytes(), b"1234")
                accepted.unlink()
                with self.assertRaisesRegex(ValueError, "too large"):
                    asyncio.run(write_temp_upload(self.upload(b"12345")))
                self.assertEqual(list(Path(tmp).glob("repopilot-*.zip")), [])

    def test_validation_error_returns_http_400_and_cleans_staging(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("api_upload.MAX_UPLOAD_BYTES", 4), patch(
                "api_upload.tempfile.tempdir", tmp
            ):
                with self.assertRaises(HTTPException) as context:
                    asyncio.run(upload_repository(self.upload(b"12345")))
                self.assertEqual(context.exception.status_code, 400)
                self.assertEqual(list(Path(tmp).glob("repopilot-*.zip")), [])

    def test_non_zip_filename_rejected_before_file_read(self):
        with self.assertRaises(HTTPException) as context:
            asyncio.run(upload_repository(self.upload(b"abc", "private.txt")))
        self.assertEqual(context.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
