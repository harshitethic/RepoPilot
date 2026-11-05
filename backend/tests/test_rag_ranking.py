import unittest

from services.rag.ranking import rank_chunks
from services.rag.signals import lexical_boost
from services.rag.types import Chunk


class RagRankingTests(unittest.TestCase):
    def test_retrieves_source_with_query_and_line_citation(self):
        chunks = [
            Chunk("src/handler.py", 30, 34, "def handle_request():\n    return request"),
            Chunk("docs/ui.md", 1, 2, "Styles and design tokens for buttons"),
        ]
        hits = rank_chunks(chunks, "handle_request")
        self.assertEqual(hits[0].chunk.path, "src/handler.py")
        self.assertEqual(hits[0].public()["citation"], "src/handler.py:L30-L34")

    def test_unrelated_results_not_returned(self):
        chunks = [Chunk("foo.py", 1, 2, "hello world")]
        self.assertEqual(rank_chunks(chunks, "absentzz"), [])
        self.assertEqual(rank_chunks(chunks, ""), [])

    def test_code_path_receives_explainable_boost(self):
        source = Chunk("src/payment_handler.py", 1, 2, "return True")
        self.assertGreater(lexical_boost(source, "payment"), 0)

    def test_invalid_limit_fails(self):
        with self.assertRaises(ValueError):
            rank_chunks([], "hello", limit=0)


if __name__ == "__main__":
    unittest.main()
