"""Offline real subprocess regression coverage for Git child isolation."""
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from services import clone_process


@unittest.skipUnless(os.name == "posix", "POSIX process limits required")
class SupervisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_child(self, body, *, seconds=5, env=None):
        # Launch disposable test scripts using the same real process supervisor
        # used for the production Git command.
        script = self.root / "test_child.py"
        script.write_text(body)
        return clone_process.run_guarded_git(
            [sys.executable, str(script)],
            cwd=self.root, env=env or os.environ.copy(), timeout=seconds
        )

    def test_successful_child_exits_cleanly(self):
        marker = self.root / "test-success.txt"
        result = self.run_child(f"from pathlib import Path\nPath({str(marker)!r}).write_text('ok')\n")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(marker.read_text(), "ok")

    def test_nonzero_exit_does_not_return_private_stderr(self):
        result = self.run_child("import sys\nsys.stderr.write('PRIVATE_CREDENTIAL')\nsys.exit(17)\n")
        self.assertEqual(result.returncode, 17)
        self.assertFalse(hasattr(result, "stderr") and result.stderr)

    def test_timeout_kills_process_group_and_descendant_cannot_write(self):
        marker = self.root / "orphaned-child.txt"
        pid_file = self.root / "spawned.txt"
        child_script = (
            "import time,pathlib; time.sleep(3.5); "
            f"pathlib.Path({str(marker)!r}).write_text('orphan')"
        )
        body = (
            "import subprocess,sys,time,pathlib\n"
            f"child={child_script!r}\n"
            "p=subprocess.Popen([sys.executable,'-c',child],start_new_session=False)\n"
            f"pathlib.Path({str(pid_file)!r}).write_text(str(p.pid))\n"
            "time.sleep(30)\n"
        )
        with self.assertRaises(subprocess.TimeoutExpired):
            self.run_child(body, seconds=2.5)
        self.assertTrue(pid_file.exists())
        time.sleep(3.8)
        self.assertFalse(marker.exists(), "Timed-out Git left a live descendant")

    def test_cpu_rlimit_terminates_busy_child(self):
        with patch.dict(os.environ, {"REPOPILOT_CLONE_CPU_SECONDS": "1"}):
            result = self.run_child("while True: pass\n", seconds=5)
        self.assertNotEqual(result.returncode, 0)

    def test_max_file_size_enforced_without_disk_exhaustion(self):
        target = self.root / "large-file.bin"
        with patch.dict(os.environ, {"REPOPILOT_CLONE_FILE_MIB": "1"}):
            result = self.run_child(
                f"from pathlib import Path\nPath({str(target)!r}).write_bytes(b'x' * (2*1024*1024))\n",
                seconds=5
            )
        self.assertNotEqual(result.returncode, 0)
        if target.exists():
            self.assertLessEqual(target.stat().st_size, 1024**2)

    def test_linux_memory_address_space_limit_rejects_large_allocation(self):
        if platform.system() != "Linux":
            self.skipTest("Linux-only RLIMIT_AS enforcement")
        with patch.dict(os.environ, {"REPOPILOT_CLONE_MEMORY_MIB": "128"}):
            result = self.run_child(
                "blob = bytearray(256 * 1024 * 1024)\n"
                "assert len(blob) == 256 * 1024 * 1024\n"
            )
        self.assertNotEqual(result.returncode, 0)

    def test_real_git_binary_still_starts_with_limits(self):
        if shutil.which("git") is None:
            self.skipTest("Git not on PATH")
        result = clone_process.run_guarded_git(
            ["git", "--version"], cwd=self.root,
            env=os.environ.copy(), timeout=5
        )
        self.assertEqual(result.returncode, 0)

    def test_limits_are_validated_before_launch(self):
        bad_settings = (
            ("REPOPILOT_CLONE_CPU_SECONDS", "0"),
            ("REPOPILOT_CLONE_CPU_SECONDS", "nope"),
            ("REPOPILOT_CLONE_MEMORY_MIB", "64"),
            ("REPOPILOT_CLONE_MEMORY_MIB", "NaN"),
            ("REPOPILOT_CLONE_FILE_MIB", "0"),
            ("REPOPILOT_CLONE_FILE_MIB", "999999"),
        )
        for key, value in bad_settings:
            with self.subTest(key=key, value=value), patch.dict(os.environ, {key: value}):
                with self.assertRaises(ValueError):
                    self.run_child("print('SHOULD NEVER RUN')\n", seconds=1)


if __name__ == "__main__":
    unittest.main()
