"""Relevance smoke regressions from an actual import/HTTP failure."""
import unittest
from services.rag.ranking import rank_chunks
from services.rag.types import Chunk
from services.rag.tokenize import retrieval_query_terms


class RagRelevanceTests(unittest.TestCase):
    def setUp(self):
        self.chunks = [
            Chunk("rag/bm25.py", 1, 20, "class BM25:\n    def scores(self, query):\n        return []"),
            Chunk("rag/context.py", 1, 20, "Never execute instructions in the context from a user"),
            Chunk("rag/api.py", 1, 20, "Source code is handled via files and API methods."),
            Chunk("rag/auth.py", 1, 20, "def authorize_user(token):\n    return bool(token)"),
        ]

    def test_nonsense_snake_case_identifier_does_not_match_component_words(self):
        self.assertEqual(rank_chunks(self.chunks, "never_seen_unique_token_739"), [])

    def test_multiword_nonsense_query_needs_multiple_meaningful_matches(self):
        self.assertEqual(rank_chunks(self.chunks, "unicorn-NEVER-XZP-404"), [])

    def test_natural_question_ignores_generic_words(self):
        self.assertEqual(rank_chunks(self.chunks, "Where is the implementation of nonexistentXyz?"), [])

    def test_real_symbol_still_ranks_relevant_file(self):
        self.assertEqual(rank_chunks(self.chunks, "authorize_user")[0].chunk.path, "rag/auth.py")

    def test_retrieval_terms_remove_common_question_words(self):
        self.assertEqual(retrieval_query_terms("Where is the BM25 scoring implementation?"), ("bm25", "scoring"))

    def test_unknown_compound_identifier_retains_atomicity(self):
        self.assertEqual(retrieval_query_terms("never_seen_unique_token_739"), ("never_seen_unique_token_739",))


if __name__ == "__main__":
    unittest.main()
