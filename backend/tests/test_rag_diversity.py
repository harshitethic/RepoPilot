import unittest

from services.rag.diversity import select_diverse
from services.rag.types import Chunk, Hit


class RagDiversityTests(unittest.TestCase):
    def test_deduplicated_source_is_preferred_over_near_match(self):
        hits = [
            Hit(Chunk("a.py", 1, 10, "alpha beta gamma delta"), 10.0),
            Hit(Chunk("a.py", 3, 12, "alpha beta gamma delta"), 9.8),
            Hit(Chunk("b.py", 1, 8, "router authentication security middleware"), 8.0),
        ]
        selection = select_diverse(hits, limit=2, relevance_weight=0.4)
        self.assertEqual(selection[0].chunk.path, "a.py")
        self.assertEqual(selection[1].chunk.path, "b.py")

    def test_empty_and_invalid_budget(self):
        self.assertEqual(select_diverse([], limit=2), [])
        with self.assertRaises(ValueError):
            select_diverse([], limit=0)
        with self.assertRaises(ValueError):
            select_diverse([], limit=1, relevance_weight=-1)


if __name__ == "__main__":
    unittest.main()
