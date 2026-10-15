"""Adversarial, network-free ZIP extraction regression tests."""
import io
import os
import stat
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services import github


class ZipImportBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repos = self.root / "repos"
        self.repos.mkdir()
        bound = patch.object(github, "BASE_DIR", self.repos)
        bound.start()
        self.addCleanup(bound.stop)

    def archive(self, members):
        filename = self.root / "fixture.zip"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(filename, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for name, contents in members:
                    archive.writestr(name, contents)
        return filename

    def test_collision_failure_does_not_delete_existing_import(self):
        existing = self.repos / ("a" * 12)
        existing.mkdir()
        keep = existing / "keep-private.txt"
        keep.write_text("private", encoding="utf-8")
        archive = self.archive([("../unsafe.py", "bad")])
        with patch.object(github.uuid, "uuid4", side_effect=[
            SimpleNamespace(hex="a" * 32), SimpleNamespace(hex="b" * 32)
        ]):
            with self.assertRaises(ValueError):
                github.extract_zip(archive)
        self.assertEqual(keep.read_text(encoding="utf-8"), "private")

    def test_duplicate_files_and_case_insensitive_aliases_are_rejected(self):
        for filenames in (["one.py", "one.py"], ["README.md", "readme.md"],
                          ["src/one.py", "src//one.py"], ["src/a.py", "src/./a.py"]):
            with self.subTest(names=filenames):
                archive = self.archive([(name, "ok") for name in filenames])
                with self.assertRaisesRegex(ValueError, "duplicate|unsafe"):
                    github.extract_zip(archive)
                self.assertEqual(list(self.repos.iterdir()), [])

    def test_symlink_file_entries_are_refused(self):
        info = zipfile.ZipInfo("inside.py")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive = self.archive([(info, "../outside")])
        with self.assertRaisesRegex(ValueError, "symlink|special|unsafe"):
            github.extract_zip(archive)
        self.assertEqual(list(self.repos.iterdir()), [])

    def test_drive_and_backslash_paths_are_rejected(self):
        for name in ("C:/outside.py", "..\\outside.py", "src\\evil.py", "src/../evil.py"):
            with self.subTest(name=name):
                archive = self.archive([(name, "not safe")])
                with self.assertRaisesRegex(ValueError, "unsafe"):
                    github.extract_zip(archive)
                self.assertEqual(list(self.repos.iterdir()), [])

    def test_file_directory_conflicts_are_rejected(self):
        for filenames in (["src", "src/inner.py"], ["src/inner.py", "src"]):
            with self.subTest(names=filenames):
                archive = self.archive([(name, "data") for name in filenames])
                with self.assertRaisesRegex(ValueError, "unsafe|conflict"):
                    github.extract_zip(archive)
                self.assertEqual(list(self.repos.iterdir()), [])

    def test_oversize_stream_rolls_back_only_new_import(self):
        existing = self.repos / ("d" * 12)
        existing.mkdir()
        (existing / "existing.txt").write_text("safe", encoding="utf-8")
        archive = self.archive([("big.py", "x" * 140)])
        with patch.object(github, "MAX_UNCOMPRESSED_BYTES", 100):
            with self.assertRaisesRegex(ValueError, "200 MB|limit"):
                github.extract_zip(archive)
        self.assertEqual((existing / "existing.txt").read_text(encoding="utf-8"), "safe")
        self.assertEqual([p.name for p in self.repos.iterdir()], ["d" * 12])

    def test_successful_id_collision_uses_new_directory_without_overwrite(self):
        previous = self.repos / ("a" * 12)
        previous.mkdir()
        (previous / "do-not-delete.txt").write_text("important", encoding="utf-8")
        archive = self.archive([("src/main.py", "print('hello')")])
        with patch.object(github.uuid, "uuid4", side_effect=[
            SimpleNamespace(hex="a" * 32), SimpleNamespace(hex="b" * 32)
        ]):
            identifier, destination = github.extract_zip(archive)
        self.assertEqual(identifier, "b" * 12)
        self.assertEqual((previous / "do-not-delete.txt").read_text(encoding="utf-8"), "important")
        self.assertEqual((destination / "src/main.py").read_text(encoding="utf-8"), "print('hello')")

    def test_streaming_beyond_reported_member_size_rolls_back(self):
        prior = self.repos / ("a" * 12)
        prior.mkdir()
        (prior / "keep.txt").write_text("important", encoding="utf-8")
        archive = self.archive([("src/main.py", "hi")])
        with patch.object(github.zipfile.ZipFile, "open", return_value=io.BytesIO(b"x" * 200)):
            with self.assertRaisesRegex(ValueError, "200 MB limit"):
                github.extract_zip(archive)
        self.assertEqual([p.name for p in self.repos.iterdir()], ["a" * 12])
        self.assertEqual((prior / "keep.txt").read_text(encoding="utf-8"), "important")

    def test_corrupt_stream_cleans_reservation(self):
        archive = self.archive([("src/main.py", "hi")])
        with patch.object(github.zipfile.ZipFile, "open",
                          side_effect=zipfile.BadZipFile("secret fixture")):
            with self.assertRaisesRegex(ValueError, "^Invalid ZIP archive"):
                github.extract_zip(archive)
        self.assertEqual(list(self.repos.iterdir()), [])

    def test_successful_nested_zip_uses_private_workspace(self):
        archive = self.archive([("src/main.py", "print('safe')"), ("README.md", "hello")])
        repo_id, path = github.extract_zip(archive)
        self.assertEqual(path.name, repo_id)
        self.assertEqual((path / "src" / "main.py").read_text(encoding="utf-8"), "print('safe')")
        self.assertEqual((path / "README.md").read_text(encoding="utf-8"), "hello")
        self.assertEqual(path.resolve().parent, self.repos.resolve())
        if os.name != "nt":
            self.assertEqual(path.stat().st_mode & 0o777, 0o700)


if __name__ == "__main__":
    unittest.main()
