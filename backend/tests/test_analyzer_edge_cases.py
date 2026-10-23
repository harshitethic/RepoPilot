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

    def test_context_ties_are_ordered_by_path(self):
        self.write("zeta.py", "shared_keyword = 1\n")
        self.write("alpha.py", "shared_keyword = 2\n")
        context = build_context(self.root, "shared_keyword", max_files=2)
        self.assertLess(context.index("--- FILE: alpha.py"), context.index("--- FILE: zeta.py"))

    def test_context_skips_oversized_match_to_include_smaller_file(self):
        self.write("a_large.py", "needle = 1\n" + "x" * 3000)
        self.write("z_small.py", "needle = 2\n")
        context = build_context(self.root, "needle", max_files=1, max_chars=150)
        self.assertIn("--- FILE: z_small.py", context)
        self.assertNotIn("--- FILE: a_large.py", context)


if __name__ == "__main__":
    unittest.main()
