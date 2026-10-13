"""Network-free repository ingestion regression tests."""
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services import github
from services.analyzer import analyze, build_context, search_code


class RepositorySafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repos = self.root / "repos"
        self.repos.mkdir()
        self.patcher = patch.object(github, "BASE_DIR", self.repos)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_github_url_host_and_path_validation(self):
        self.assertEqual(
            github.validate_github_url("https://github.com/example/example-repo.git"),
            "https://github.com/example/example-repo.git",
        )
        for url in (
            "https://evil.example/example/repo", "file:///etc/passwd",
            "https://github.com/../repo",
            "https://github.com/example/repo/blob/main",
            "https://github.com/example",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                github.validate_github_url(url)

    def test_repo_ids_cannot_escape_import_directory(self):
        rid = "a" * 12
        folder = self.repos / rid
        folder.mkdir()
        self.assertEqual(github.safe_repo_path(rid), folder.resolve())
        for name in ("../secret", "/tmp", "1" * 13, "ABCDEFABCDEF"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                github.safe_repo_path(name)
        with self.assertRaises(FileNotFoundError):
            github.safe_repo_path("b" * 12)

    def test_symlink_files_are_excluded_from_analyzer(self):
        imported = self.repos / ("a" * 12)
        imported.mkdir()
        (imported / "README.md").write_text("ok\n")
        outside = self.root / "private.env"
        outside.write_text("CONFIDENTIAL_MARKER\n")
        try:
            (imported / "credentials.py").symlink_to(outside)
        except OSError:
            self.skipTest("File symlinks not available")
        self.assertEqual([p.name for p in github.iter_files(imported)], ["README.md"])
        self.assertNotIn("CONFIDENTIAL_MARKER", str(analyze(imported)))
        self.assertNotIn("CONFIDENTIAL_MARKER", build_context(imported, "credentials.py"))

    def test_gitignore_detected_and_line_count_accurate(self):
        imported = self.repos / ("a" * 12)
        imported.mkdir()
        (imported / ".gitignore").write_text("node_modules\n")
        (imported / "README.md").write_text("one\ntwo\n")
        result = analyze(imported)
        self.assertTrue(result["signals"]["gitignore"])
        self.assertEqual(next(f["lines"] for f in result["files"] if f["path"] == "README.md"), 2)

    def test_blank_search_does_not_dump_first_lines(self):
        imported = self.repos / ("a" * 12)
        imported.mkdir()
        (imported / "main.py").write_text("PRIVATE_TEXT\n")
        self.assertEqual(search_code(imported, "  "), [])

    def test_valid_zip_is_extracted_within_repo(self):
        z = self.root / "safe.zip"
        with zipfile.ZipFile(z, "w") as archive:
            archive.writestr("src/main.py", "print('ok')")
        rid, dest = github.extract_zip(z)
        self.assertEqual(github.safe_repo_path(rid), dest.resolve())
        self.assertEqual((dest / "src/main.py").read_text(), "print('ok')")

    def test_zip_slip_is_refused_without_writing_outside(self):
        for archive_name in ("../escape.py", "/tmp/escape.py"):
            with self.subTest(archive_name=archive_name):
                z = self.root / "bad.zip"
                with zipfile.ZipFile(z, "w") as archive:
                    archive.writestr(archive_name, "malicious")
                with self.assertRaisesRegex(ValueError, "unsafe"):
                    github.extract_zip(z)
                self.assertFalse((self.root / "escape.py").exists())


if __name__ == "__main__":
    unittest.main()
