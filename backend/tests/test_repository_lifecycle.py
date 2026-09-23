import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from services import github


class RepositoryLifecycleTests(unittest.TestCase):
    def make_repo(self, root: Path, repo_id: str, files=None) -> Path:
        repo = root / repo_id
        repo.mkdir(parents=True)
        for name, content in (files or {}).items():
            target = repo / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        return repo

    def test_repository_summary_reports_size_and_file_count(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo_id = "a" * 12
            self.make_repo(
                root,
                repo_id,
                {"a.txt": "abc", "src/b.py": "print('ok')\n"},
            )

            with patch("services.github.BASE_DIR", root):
                summary = github.repository_summary(repo_id)

            self.assertEqual(summary["repo_id"], repo_id)
            self.assertEqual(summary["file_count"], 2)
            self.assertEqual(summary["total_bytes"], 15)
            self.assertIn("+00:00", summary["updated_at"])

    def test_capacity_guard_blocks_new_repository_when_full(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_repo(root, "a" * 12)
            self.make_repo(root, "b" * 12)

            with (
                patch("services.github.BASE_DIR", root),
                patch("services.github.MAX_REPOSITORIES", 2),
            ):
                with self.assertRaisesRegex(RuntimeError, "capacity reached"):
                    github.ensure_repository_capacity()

    def test_cleanup_repositories_deletes_only_expired_repositories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            old = self.make_repo(root, "a" * 12)
            fresh = self.make_repo(root, "b" * 12)
            now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
            old_ts = now.timestamp() - 48 * 60 * 60
            fresh_ts = now.timestamp() - 2 * 60 * 60
            os.utime(old, (old_ts, old_ts))
            os.utime(fresh, (fresh_ts, fresh_ts))

            with patch("services.github.BASE_DIR", root):
                deleted = github.cleanup_repositories(24, now=now)

            self.assertEqual(deleted, ["a" * 12])
            self.assertFalse(old.exists())
            self.assertTrue(fresh.exists())

    def test_delete_repository_is_scoped_to_valid_repository_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = self.make_repo(root, "a" * 12)
            second = self.make_repo(root, "b" * 12)

            with patch("services.github.BASE_DIR", root):
                github.delete_repository("a" * 12)
                with self.assertRaises(ValueError):
                    github.delete_repository("../outside")

            self.assertFalse(first.exists())
            self.assertTrue(second.exists())


if __name__ == "__main__":
    unittest.main()
