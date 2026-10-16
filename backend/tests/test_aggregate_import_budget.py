"""Network-free persistent-storage and concurrent-import admission tests."""
import os
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from services import github


class AggregateImportBudgetTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.imports = self.root / "imports"
        self.imports.mkdir()
        bound = patch.object(github, "BASE_DIR", self.imports)
        bound.start()
        self.addCleanup(bound.stop)

    def make_zip(self, name="fixture.zip", data=b"abc") -> Path:
        path = self.root / name
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("src/data.py", data)
        return path

    def existing_repo(self, contents: bytes=b"abcd") -> Path:
        path = self.imports / ("a" * 12)
        path.mkdir()
        (path / "keep.txt").write_bytes(contents)
        return path

    def test_storage_config_validation_and_default(self):
        self.assertEqual(github.configured_storage_limit(), 2 * 1024**3)
        for invalid in ("0", "-1", "2.0", "abc", str(1024**4 + 1)):
            with self.subTest(invalid=invalid), patch.dict(os.environ, {
                "REPOPILOT_MAX_STORAGE_BYTES": invalid
            }):
                with self.assertRaises(ValueError):
                    github.configured_storage_limit()

    def test_existing_storage_blocks_zip_before_creating_any_workspace(self):
        original = self.existing_repo(b"1234567")
        data = self.make_zip(data=b"abcd")
        with patch.dict(os.environ, {"REPOPILOT_MAX_STORAGE_BYTES": "10"}):
            with self.assertRaisesRegex(ValueError, "storage capacity"):
                github.extract_zip(data)
        self.assertEqual(github.repository_ids(), ["a" * 12])
        self.assertEqual((original / "keep.txt").read_bytes(), b"1234567")

    def test_exact_budget_is_accepted_and_reclaimed_after_delete(self):
        data = self.make_zip(data=b"abcde")
        with patch.dict(os.environ, {"REPOPILOT_MAX_STORAGE_BYTES": "5"}):
            first_id, first = github.extract_zip(data)
            self.assertEqual(github.stored_repository_bytes(), 5)
            with self.assertRaisesRegex(ValueError, "storage capacity"):
                github.extract_zip(data)
            self.assertEqual(github.repository_ids(), [first_id])
            github.delete_repository(first_id)
            second_id, second = github.extract_zip(data)
            self.assertEqual((second / "src/data.py").read_bytes(), b"abcde")
            self.assertNotEqual(first_id, second_id)

    def test_clone_over_budget_rolls_back_only_its_reserved_workspace(self):
        original = self.existing_repo(b"keep")
        def simulated_git_clone(argv, **kwargs):
            Path(argv[-1], "large.bin").write_bytes(b"x" * 25)
            return SimpleNamespace(returncode=0)

        with patch.dict(os.environ, {"REPOPILOT_MAX_STORAGE_BYTES": "20"}), patch.object(
            github, "run_guarded_git", side_effect=simulated_git_clone
        ):
            with self.assertRaisesRegex(ValueError, "storage capacity reached after clone"):
                github.clone_repo("https://github.com/example/repository")
        self.assertEqual(github.repository_ids(), ["a" * 12])
        self.assertEqual((original / "keep.txt").read_bytes(), b"keep")

    def test_unreadable_storage_is_fail_closed(self):
        self.existing_repo()
        with patch.object(github, "directory_bytes", side_effect=OSError("secret")):
            with self.assertRaisesRegex(ValueError, "inspect repository storage"):
                github.ensure_repository_capacity()

    def test_concurrent_zip_count_limit_is_admitted_atomically(self):
        data = self.make_zip(data=b"data")
        original_reserve = github.reserve_repository_directory

        def slow_reserve():
            # Without a cross-thread admission lock, both requests pass the
            # count check during this pause and create two reservations.
            time.sleep(0.15)
            return original_reserve()

        with patch.dict(os.environ, {"REPOPILOT_MAX_REPOSITORIES": "1"}), patch.object(
            github, "reserve_repository_directory", side_effect=slow_reserve
        ):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: self._try_import(data), range(2)))
        self.assertEqual(results.count("ok"), 1, results)
        self.assertEqual(results.count("rejected"), 1, results)
        self.assertEqual(len(github.repository_ids()), 1)

    def test_concurrent_zip_storage_limit_is_atomic(self):
        first_zip = self.make_zip(name="first.zip", data=b"1234")
        second_zip = self.make_zip(name="second.zip", data=b"abcd")
        original_reserve = github.reserve_repository_directory

        def slow_reserve():
            time.sleep(0.10)
            return original_reserve()

        with patch.dict(os.environ, {"REPOPILOT_MAX_STORAGE_BYTES": "6"}), patch.object(
            github, "reserve_repository_directory", side_effect=slow_reserve
        ):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(self._try_import, [first_zip, second_zip]))
        self.assertEqual(results.count("ok"), 1, results)
        self.assertEqual(results.count("rejected"), 1, results)
        self.assertEqual(github.stored_repository_bytes(), 4)
        self.assertEqual(len(github.repository_ids()), 1)

    def _try_import(self, archive):
        try:
            github.extract_zip(archive)
            return "ok"
        except ValueError as exc:
            self.assertIn("capacity reached", str(exc))
            return "rejected"

    def test_processes_share_admission_lock(self):
        data = self.make_zip(data=b"data")
        script = '''
import os,sys,time
from pathlib import Path
from services import github
github.BASE_DIR=Path(sys.argv[1])
original=github.reserve_repository_directory
def slow_reserve():
    time.sleep(0.25)
    return original()
github.reserve_repository_directory=slow_reserve
try:
    github.extract_zip(Path(sys.argv[2]))
    print("ok")
except ValueError:
    print("rejected")
'''
        python = sys.executable
        env = dict(os.environ, REPOPILOT_MAX_REPOSITORIES="1")
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
        jobs = [
            subprocess.Popen(
                [python, "-c", script, str(self.imports), str(data)],
                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            for _ in range(2)
        ]
        result = [job.communicate(timeout=15) for job in jobs]
        for job, (stdout, stderr) in zip(jobs, result):
            self.assertEqual(job.returncode, 0, stderr)
        self.assertEqual(sorted(stdout.strip() for stdout, _ in result), ["ok", "rejected"])
        self.assertEqual(len(github.repository_ids()), 1)


if __name__ == "__main__":
    unittest.main()
