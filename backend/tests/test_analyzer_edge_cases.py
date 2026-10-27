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

    def test_long_minified_line_shows_the_actual_match_within_bounded_snippet(self):
        self.write("minified.js", "x" * 800 + "NeedleToken" + "y" * 800 + "\\n")
        found = search_code(self.root, "needletoken")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["line"], 1)
        self.assertIn("NeedleToken", found[0]["text"])
        self.assertLessEqual(len(found[0]["text"]), 300)
        self.assertTrue(found[0]["text"].startswith("..."))
        self.assertTrue(found[0]["text"].endswith("..."))

    def test_long_line_unicode_casefold_offset_does_not_shift_snippet(self):
        self.write("unicode.js", "ß" * 440 + "RareNeedle" + "x" * 420 + "\\n")
        found = search_code(self.root, "rareneedle")
        self.assertEqual(len(found), 1)
        self.assertIn("RareNeedle", found[0]["text"])
        self.assertLessEqual(len(found[0]["text"]), 300)

    def test_search_zero_or_negative_limit_never_emits_results(self):
        self.write("example.py", "needle = 42")
        for limit in (0, -1, -100):
            with self.subTest(limit=limit):
                self.assertEqual(search_code(self.root, "needle", limit=limit), [])

    def test_short_line_snippet_is_unchanged(self):
        self.write("short.py", "    needle = 42   ")
        self.assertEqual(search_code(self.root, "needle")[0]["text"], "needle = 42")

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

    def test_context_query_match_ranks_above_filename_bonus(self):
        self.write("README.md", "This file does not mention the symbol.")
        self.write("worker.py", "def exact_unique_symbol(): pass")
        context = build_context(self.root, "exact_unique_symbol", max_files=1)
        self.assertIn("worker.py", context)
        self.assertNotIn("README.md", context)

    def test_context_identifies_symbols_surrounded_by_code_punctuation(self):
        self.write("a_unrelated.py", "no matching function here")
        self.write("z_worker.py", "def process_job(): pass")
        context = build_context(self.root, "Where is `process_job()` defined?", max_files=1)
        self.assertIn("z_worker.py", context)
        self.assertNotIn("a_unrelated.py", context)

    def test_context_unicode_casefold_matches_source_content(self):
        self.write("a_unrelated.py", "nothing to see here")
        self.write("z_relevant.py", "straße_feature = 1")
        context = build_context(self.root, "STRASSE_FEATURE", max_files=1)
        self.assertIn("z_relevant.py", context)
        self.assertNotIn("a_unrelated.py", context)

    def test_context_skips_oversized_match_to_include_smaller_file(self):
        self.write("a_large.py", "needle = 1\n" + "x" * 3000)
        self.write("z_small.py", "needle = 2\n")
        context = build_context(self.root, "needle", max_files=1, max_chars=150)
        self.assertIn("--- FILE: z_small.py", context)
        self.assertNotIn("--- FILE: a_large.py", context)

    def test_context_budget_counts_included_not_considered_files(self):
        self.write("a_large.py", "needle = 1\n" + "x" * 3000)
        self.write("b_small.py", "needle = 2\n")
        self.write("c_small.py", "needle = 3\n")
        context = build_context(self.root, "needle", max_files=2, max_chars=250)
        self.assertIn("--- FILE: b_small.py", context)
        self.assertIn("--- FILE: c_small.py", context)
        self.assertNotIn("--- FILE: a_large.py", context)


    def test_context_selected_file_exposes_the_query_match(self):
        self.write("a_hidden.py", "x" * 5000 + "needle_for_context")
        self.write("z_visible.py", "needle_for_context = 42")
        context = build_context(self.root, "needle_for_context", max_files=1)
        self.assertIn("z_visible.py", context)
        self.assertIn("needle_for_context = 42", context)
        self.assertNotIn("a_hidden.py", context)


    def test_unmatched_question_does_not_return_unrelated_readme(self):
        self.write("README.md", "setup notes without the requested identifier")
        self.write("app.py", "def start(): pass")
        context = build_context(self.root, "nonexistent_unique_identifier")
        self.assertIn("No strongly matching files", context)
        self.assertNotIn("setup notes", context)


if __name__ == "__main__":
    unittest.main()
