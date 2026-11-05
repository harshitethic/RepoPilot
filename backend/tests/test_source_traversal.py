import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.github import iter_files


class SourceTraversalTests(unittest.TestCase):
    def test_walk_skips_file_checks_in_ignored_subtrees(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ignored = root / "src" / "Node_Modules"
            ignored.mkdir(parents=True)
            dependency = ignored / "vendor.js"
            dependency.touch()
            source = root / "src" / "app.js"
            source.touch()
            inspected = []
            is_file = Path.is_file

            def track_file_check(path):
                inspected.append(path)
                return is_file(path)

            with patch.object(Path, "is_file", track_file_check):
                self.assertEqual(list(iter_files(root)), [source])
            self.assertNotIn(dependency, inspected)
