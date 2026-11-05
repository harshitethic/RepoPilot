import unittest

from services.rag.context import format_evidence, references
from services.rag.types import Chunk, Hit


class RagContextTests(unittest.TestCase):
    def setUp(self):
        self.hits = [
            Hit(Chunk("src/models.py", 10, 18, "example " * 600), 4.1),
            Hit(Chunk("src/api.py", 2, 6, "def get(): return 200"), 2.3),
        ]

    def test_context_respects_character_budget(self):
        for limit in (0, 40, 180, 700, 3000, 12000):
            with self.subTest(limit=limit):
                self.assertLessEqual(len(format_evidence(self.hits, char_budget=limit)), limit)

    def test_citations_exactly_match_source_lines(self):
        self.assertEqual(references(self.hits)[0], {
            "citation": "src/models.py:L10-L18",
            "path": "src/models.py",
            "start_line": 10,
            "end_line": 18,
        })

    def test_no_source_cannot_invent_context(self):
        self.assertEqual(format_evidence([]), "")
        with self.assertRaises(ValueError):
            format_evidence(self.hits, char_budget=-1)


if __name__ == "__main__":
    unittest.main()
