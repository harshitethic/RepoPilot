"""Network-free repository ingestion regression tests."""
import os
import subprocess
import sys
from types import SimpleNamespace
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

    def test_github_url_rejects_credentials_ports_queries_fragments_and_plain_http(self):
        valid = {
            "https://github.com/example/repo": "https://github.com/example/repo.git",
            "https://www.github.com/Example/Repo.git": "https://github.com/Example/Repo.git",
            "https://GITHUB.COM/example/repo": "https://github.com/example/repo.git",
        }
        for url, expected in valid.items():
            with self.subTest(url=url):
                self.assertEqual(github.validate_github_url(url), expected)
        invalid = (
            "http://github.com/example/repo",
            "https://user:password@github.com/example/repo",
            "https://user@github.com/example/repo",
            "https://github.com:443/example/repo",
            "https://github.com/example/repo?token=private",
            "https://github.com/example/repo#revision",
            "https://github.com/example/.git",
            "https://github.com/-invalid/repo",
            "https://github.com/example/repo;path=unsafe",
            "https://github.com/example/repo/extra",
            "https://github.com/example/repo%2fother",
            "https://github.com:bad/example/repo",
        )
        for url in invalid:
            with self.subTest(url=url), self.assertRaises(ValueError):
                github.validate_github_url(url)

    def test_clone_ignores_hostile_git_config_and_disables_helpers(self):
        with patch.dict(os.environ, {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "url.file:///tmp/redirect.insteadOf",
            "GIT_CONFIG_VALUE_0": "https://github.com/",
            "GIT_ASKPASS": "/tmp/malicious-askpass",
            "SSH_ASKPASS": "/tmp/malicious-askpass",
            "LD_PRELOAD": "/tmp/malicious-preload",
        }):
            with patch.object(github, "run_guarded_git", return_value=SimpleNamespace(returncode=0)) as runner:
                identifier, dest = github.clone_repo("https://github.com/Example/Project.git")
        self.assertEqual(len(identifier), 12)
        self.assertTrue(dest.is_dir())
        self.assertEqual(dest.parent, self.repos)
        args, kwargs = runner.call_args
        self.assertIn("https://github.com/Example/Project.git", args[0])
        self.assertEqual(args[0][0], "git")
        self.assertIn("core.hooksPath=" + os.devnull, args[0])
        self.assertIn("core.fsmonitor=false", args[0])
        self.assertIn("credential.helper=", args[0])
        self.assertIn("protocol.ext.allow=never", args[0])
        self.assertEqual(kwargs["timeout"], 90)
        self.assertEqual(kwargs["cwd"], self.repos)
        for prohibited in ("GIT_CONFIG_COUNT", "GIT_CONFIG_KEY_0", "GIT_CONFIG_VALUE_0",
                           "SSH_ASKPASS", "LD_PRELOAD"):
            self.assertNotIn(prohibited, kwargs["env"])
        self.assertEqual(kwargs["env"]["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertEqual(kwargs["env"]["GIT_CONFIG_GLOBAL"], os.devnull)
        self.assertEqual(kwargs["env"]["GIT_TERMINAL_PROMPT"], "0")

    def test_clone_id_collision_preserves_preexisting_import(self):
        first = self.repos / ("a" * 12)
        first.mkdir()
        existing = first / "do-not-delete.txt"
        existing.write_text("valuable")
        with patch.object(github.uuid, "uuid4", side_effect=[
            SimpleNamespace(hex="a" * 32),
            SimpleNamespace(hex="b" * 32),
        ]):
            with patch.object(github, "run_guarded_git", return_value=SimpleNamespace(returncode=0)):
                identifier, dest = github.clone_repo("https://github.com/Example/Project")
        self.assertEqual(identifier, "b" * 12)
        self.assertTrue(dest.is_dir())
        self.assertEqual(existing.read_text(), "valuable")

    def test_failed_clone_removes_only_reserved_directory_without_leaking_stderr(self):
        with patch.object(github.uuid, "uuid4", return_value=SimpleNamespace(hex="c" * 32)):
            with patch.object(github, "run_guarded_git", return_value=SimpleNamespace(
                returncode=128, stderr=b"private-token-should-never-be-sent-to-client"
            )):
                with self.assertRaises(RuntimeError) as context:
                    github.clone_repo("https://github.com/Example/Project")
        self.assertNotIn("private-token", str(context.exception))
        self.assertFalse((self.repos / ("c" * 12)).exists())

    def test_clone_timeout_cleans_reservation_without_touching_existing_repos(self):
        previous = self.repos / ("e" * 12)
        previous.mkdir()
        (previous / "keep.txt").write_text("unchanged")
        with patch.object(github.uuid, "uuid4", return_value=SimpleNamespace(hex="d" * 32)):
            with patch.object(github, "run_guarded_git",
                              side_effect=subprocess.TimeoutExpired(["git", "clone"], 90)):
                with self.assertRaisesRegex(RuntimeError, "timed out"):
                    github.clone_repo("https://github.com/Example/Project")
        self.assertFalse((self.repos / ("d" * 12)).exists())
        self.assertEqual((previous / "keep.txt").read_text(), "unchanged")

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