import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError
from services import github
from app import Cleanup, cleanup_repositories_endpoint, remove_repository


class RepositoryLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "imports"
        self.root.mkdir()
        self.patcher = patch("services.github.BASE_DIR", self.root)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def repo(self, repo_id, files=None):
        path = self.root / repo_id
        path.mkdir()
        for filename, content in (files or {}).items():
            file = path / filename
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(content)
        return path

    def test_lists_repository_files_sizes_and_timestamps(self):
        rid = "a" * 12
        self.repo(rid, {"README.md": "abc", "src/file.py": "hello"})
        output = github.list_repositories()
        self.assertEqual(len(output), 1)
        self.assertEqual(output[0]["repo_id"], rid)
        self.assertEqual(output[0]["file_count"], 2)
        self.assertEqual(output[0]["total_bytes"], 8)
        self.assertIn("+00:00", output[0]["updated_at"])

    def test_capacity_guard_and_invalid_settings(self):
        self.repo("a" * 12)
        with patch.dict(os.environ, {"REPOPILOT_MAX_REPOSITORIES": "1"}):
            with self.assertRaisesRegex(ValueError, "capacity reached"):
                github.ensure_repository_capacity()
        for invalid in ("0", "99999", "abc"):
            with patch.dict(os.environ, {"REPOPILOT_MAX_REPOSITORIES": invalid}):
                with self.assertRaises(ValueError):
                    github.configured_repository_limit()

    def test_symlinked_imports_never_enumerated_or_deleted(self):
        outside = Path(self.temp.name) / "external"
        outside.mkdir()
        (outside / "secret").write_text("external")
        try:
            (self.root / ("a" * 12)).symlink_to(outside, target_is_directory=True)
        except (NotImplementedError, OSError):
            self.skipTest("Symlinks unavailable")
        self.assertEqual(github.repository_ids(), [])
        with self.assertRaises(ValueError):
            github.safe_repo_path("a" * 12)
        with self.assertRaises(ValueError):
            github.delete_repository("a" * 12)
        self.assertTrue((outside / "secret").exists())

    def test_cleanup_is_preview_only_until_explicitly_executed(self):
        old = self.repo("a" * 12)
        fresh = self.repo("b" * 12)
        now = datetime(2026, 10, 13, 8, tzinfo=timezone.utc)
        os.utime(old, (now.timestamp() - 48 * 3600,) * 2)
        os.utime(fresh, (now.timestamp() - 2 * 3600,) * 2)
        preview = github.cleanup_repositories(24, now=now)
        self.assertEqual(preview, {"candidates": ["a" * 12], "deleted": []})
        self.assertTrue(old.exists())
        actual = github.cleanup_repositories(24, dry_run=False, now=now)
        self.assertEqual(actual["deleted"], ["a" * 12])
        self.assertFalse(old.exists())
        self.assertTrue(fresh.exists())

    def test_delete_scopes_id_and_retains_sibling_import(self):
        first = self.repo("a" * 12)
        second = self.repo("b" * 12)
        with self.assertRaises(HTTPException) as error:
            remove_repository("../outside")
        self.assertEqual(error.exception.status_code, 400)
        self.assertTrue(first.exists())
        github.delete_repository("a" * 12)
        self.assertFalse(first.exists())
        self.assertTrue(second.exists())

    def test_cleanup_endpoint_dry_run_default_and_bounds(self):
        self.assertTrue(Cleanup().dry_run)
        self.assertEqual(Cleanup().max_age_hours, 24)
        for value in (0, 721):
            with self.assertRaises(ValidationError):
                Cleanup(max_age_hours=value)
        with self.assertRaises(ValueError):
            github.cleanup_repositories(0)
        result = cleanup_repositories_endpoint(Cleanup())
        self.assertEqual(result["deleted"], [])
        self.assertTrue(result["dry_run"])


if __name__ == "__main__":
    unittest.main()
