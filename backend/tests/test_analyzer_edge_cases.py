"""Focused regressions for repository search and local AI context assembly."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.analyzer import build_context, search_code


class AnalyzerEdgeCaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_unicode_casefold_finds_non_ascii_equivalents(self):
        self.write("example.py", "STRASSE = 'ok'\n")
        matches = search_code(self.root, "straße")
        self.assertEqual([(row["path"], row["line"]) for row in matches], [("example.py", 1)])

    def test_search_results_use_stable_path_order(self):
        self.write("z_last.py", "needle = 2\n")
        self.write("a_first.py", "needle = 1\n")
        self.assertEqual(
            [row["path"] for row in search_code(self.root, "needle")],
            ["a_first.py", "z_last.py"],
        )


if __name__ == "__main__":
    unittest.main()
