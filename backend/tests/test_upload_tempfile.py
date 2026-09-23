import asyncio
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import UploadFile

from api_upload import write_temp_upload


class UploadTempFileTests(unittest.TestCase):
    def make_upload(self, data):
        return UploadFile(filename="repository.zip", file=io.BytesIO(data))

    def test_each_upload_gets_a_unique_temp_file(self):
        first = asyncio.run(write_temp_upload(self.make_upload(b"first")))
        second = asyncio.run(write_temp_upload(self.make_upload(b"second")))
        try:
            self.assertNotEqual(first, second)
            self.assertEqual(first.read_bytes(), b"first")
            self.assertEqual(second.read_bytes(), b"second")
        finally:
            first.unlink(missing_ok=True)
            second.unlink(missing_ok=True)

    def test_oversized_upload_is_removed_after_streaming_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch("api_upload.MAX_UPLOAD_BYTES", 4),
                patch("api_upload.tempfile.tempdir", temp_dir),
            ):
                with self.assertRaisesRegex(ValueError, "too large"):
                    asyncio.run(
                        write_temp_upload(self.make_upload(b"12345"))
                    )

            leftovers = list(Path(temp_dir).glob("repopilot-*.zip"))
            self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
