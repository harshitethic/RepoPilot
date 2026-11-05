import tempfile
import unittest
from pathlib import Path

from services.rag.corpus import scan_corpus


class RagCorpusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "src").mkdir()
        (self.root / "docs").mkdir()
        (self.root / "src" / "app.py").write_text("def foo():\n    return 42\n", encoding="utf-8")
        (self.root / "docs" / "readme.md").write_text("This documents foo.", encoding="utf-8")
        (self.root / "ignore.bin").write_bytes(b"foo\x00bar")

    def test_scans_supported_files_with_stable_paths(self):
        hits = scan_corpus(self.root)
        self.assertEqual([h.path for h in hits], ["docs/readme.md", "src/app.py"])

    def test_prefix_is_component_anchored(self):
        self.assertEqual([h.path for h in scan_corpus(self.root, path_prefix="src")], ["src/app.py"])
        self.assertEqual(scan_corpus(self.root, path_prefix="s"), [])

    def test_path_traversal_and_backslashes_rejected(self):
        for prefix in ("../", "/tmp", "src/../docs", r"src\docs", ""):
            with self.subTest(prefix=prefix), self.assertRaises(ValueError):
                scan_corpus(self.root, path_prefix=prefix)

    def test_budgets_limit_work(self):
        self.assertEqual(len(scan_corpus(self.root, max_files=1)), 1)
        self.assertEqual(len(scan_corpus(self.root, max_chunks=1)), 1)
        with self.assertRaises(ValueError):
            scan_corpus(self.root, max_chunks=0)


if __name__ == "__main__":
    unittest.main()
