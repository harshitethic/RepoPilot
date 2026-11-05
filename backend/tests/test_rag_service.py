import tempfile
import unittest
from pathlib import Path

from services.rag.service import retrieve


class RagServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "database.py").write_text(
            "def open_database():\n    return connection\n", encoding="utf-8"
        )
        (self.root / "styles.css").write_text("body { color: red; }", encoding="utf-8")

    def test_question_retrieves_actual_file(self):
        hits = retrieve(self.root, "open_database")
        self.assertTrue(hits)
        self.assertEqual(hits[0].chunk.path, "database.py")

    def test_nonsense_query_refuses_to_guess(self):
        self.assertEqual(retrieve(self.root, "a9xneverexistsz"), [])

    def test_invalid_question_refused(self):
        for bad in (" ", "x" * 1201):
            with self.subTest(bad=bad[:10]), self.assertRaises(ValueError):
                retrieve(self.root, bad)


if __name__ == "__main__":
    unittest.main()
