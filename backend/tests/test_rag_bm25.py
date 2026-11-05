import unittest

from services.rag.bm25 import BM25
from services.rag.types import Chunk


class BM25Tests(unittest.TestCase):
    def setUp(self):
        self.chunks = [
            Chunk("a.py", 1, 4, "database transaction rollback isolation"),
            Chunk("b.py", 1, 4, "frontend layout button theme"),
            Chunk("c.py", 1, 4, "database query rollback rollback"),
        ]

    def test_relevant_chunks_score_above_unrelated(self):
        scores = BM25(self.chunks).scores("database rollback")
        self.assertGreater(scores[2], scores[1])
        self.assertGreater(scores[0], scores[1])
        self.assertEqual(scores[1], 0)

    def test_unknown_terms_and_empty_index(self):
        self.assertEqual(BM25(self.chunks).scores("unseen_xyz"), [0, 0, 0])
        self.assertEqual(BM25([]).scores("anything"), [])

    def test_invalid_tuning_is_rejected(self):
        with self.assertRaises(ValueError):
            BM25(self.chunks, b=1.1)
        with self.assertRaises(ValueError):
            BM25(self.chunks, k1=0)


if __name__ == "__main__":
    unittest.main()
