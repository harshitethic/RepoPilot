import unittest

from api_upload import write_temp_upload


class UploadTempFileTests(unittest.TestCase):
    def test_each_upload_gets_a_unique_temp_file(self):
        first = write_temp_upload(b"first")
        second = write_temp_upload(b"second")
        try:
            self.assertNotEqual(first, second)
            self.assertEqual(first.read_bytes(), b"first")
            self.assertEqual(second.read_bytes(), b"second")
        finally:
            first.unlink(missing_ok=True)
            second.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
