import tempfile
import unittest
from pathlib import Path

from services.github import iter_files


class RepositoryFileBoundaryTests(unittest.TestCase):
    def test_external_symlink_is_not_indexed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / "repo"
            repo.mkdir()
            outside = root / "outside.py"
            outside.write_text("SECRET = True\n", encoding="utf-8")
            link = repo / "linked.py"
            try:
                link.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks are unavailable on this platform")

            indexed = list(iter_files(repo))

            self.assertEqual(indexed, [])

    def test_internal_file_is_still_indexed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            source = repo / "src" / "main.py"
            source.parent.mkdir()
            source.write_text("print('ok')\n", encoding="utf-8")

            indexed = list(iter_files(repo))

            self.assertEqual(indexed, [source.resolve()])


if __name__ == "__main__":
    unittest.main()
