"""Validate the published fictional ZIP against the actual local HTTP API.

The demonstration is offline and does not test a live model.
"""
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import httpx
from app import app
from services import github

ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "examples" / "create_demo_zip.py"


def generate_archive(path: Path) -> bytes:
    completed = subprocess.run(
        [sys.executable, str(GENERATOR), "--output", str(path)],
        cwd=ROOT, capture_output=True, text=True, check=True, timeout=20
    )
    assert completed.stdout.strip() == str(path)
    return path.read_bytes()


class PublishedDemoZipTests(unittest.TestCase):
    def test_generator_is_reproducible_and_contains_searchable_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = generate_archive(root / "first.zip")
            second = generate_archive(root / "second.zip")
            self.assertEqual(first, second)
            with zipfile.ZipFile(root / "first.zip") as archive:
                paths = set(archive.namelist())
                self.assertIn("README.md", paths)
                self.assertIn("src/catalog.py", paths)
                self.assertIn("src/api.py", paths)
                self.assertIn("find_title", archive.read("src/catalog.py").decode("utf-8"))
                self.assertTrue(all(
                    member.date_time == (1980, 1, 1, 0, 0, 0)
                    and member.create_system == 3
                    and member.external_attr >> 16 == 0o100644
                    for member in archive.infolist()
                ))
                self.assertTrue(
                    all(not p.startswith("/") and ".." not in Path(p).parts for p in paths)
                )

    def test_generator_does_not_overwrite_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "existing.zip"
            sentinel = b"EXISTING_DOCUMENT_DO_NOT_TOUCH"
            destination.write_bytes(sentinel)
            result = subprocess.run(
                [sys.executable, str(GENERATOR), "--output", str(destination)],
                cwd=ROOT, capture_output=True, text=True, timeout=20
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("already exists", result.stderr.lower())
            self.assertEqual(destination.read_bytes(), sentinel)


    @unittest.skipIf(sys.platform == "win32", "Windows symlink setup needs special privileges")
    def test_generator_does_not_follow_existing_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "important.txt"
            sentinel = b"DO_NOT_REPLACE_SYMLINK_TARGET"
            target.write_bytes(sentinel)
            link = root / "fictional-catalog.zip"
            link.symlink_to(target)
            result = subprocess.run(
                [sys.executable, str(GENERATOR), "--output", str(link)],
                cwd=ROOT, capture_output=True, text=True, timeout=20
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("already exists", result.stderr.lower())
            self.assertTrue(link.is_symlink())
            self.assertEqual(target.read_bytes(), sentinel)



class PublishedDemoHttpTests(unittest.IsolatedAsyncioTestCase):
    async def test_published_zip_imports_searches_and_deletes_without_ollama(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive_path = root / "fictional-catalog.zip"
            generate_archive(archive_path)
            imports = root / "imports"
            imports.mkdir()
            with patch.object(github, "BASE_DIR", imports):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="http://local.test",
                ) as client:
                    upload = await client.post(
                        "/api/upload",
                        files={
                            "file": (
                                "fictional-catalog.zip",
                                archive_path.read_bytes(),
                                "application/zip",
                            )
                        },
                    )
                    self.assertEqual(upload.status_code, 200, upload.text)
                    repo_id = upload.json()["repo_id"]
                    self.assertTrue((imports / repo_id / "src/catalog.py").is_file())
                    result = await client.post(
                        "/api/search", json={"repo_id": repo_id, "query": "find_title"}
                    )
                    self.assertEqual(result.status_code, 200, result.text)
                    matches = result.json()["results"]
                    self.assertTrue(
                        any(row["path"] == "src/catalog.py" and row["line"] == 2 for row in matches),
                        matches,
                    )
                    deleted = await client.delete(f"/api/repositories/{repo_id}")
                    self.assertEqual(deleted.status_code, 200, deleted.text)
                    self.assertFalse((imports / repo_id).exists())


if __name__ == "__main__":
    unittest.main()
