import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.github import iter_files


class SourceTraversalTests(unittest.TestCase):
    def test_walk_skips_ignored_subtrees_before_opening_them(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ignored = root / "src" / "Node_Modules"
            ignored.mkdir(parents=True)
            (ignored / "vendor.js").touch()
            source = root / "src" / "app.js"
            source.touch()
            scanned = []
            scandir = os.scandir

            def record_scan(path):
                scanned.append(Path(path))
                return scandir(path)

            with patch("os.scandir", side_effect=record_scan):
                self.assertEqual(list(iter_files(root)), [source])
            self.assertNotIn(ignored, scanned)
