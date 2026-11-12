import unittest

from services.rag.ranking import rank_chunks
from services.rag.tokenize import retrieval_query_terms, tokenize
from services.rag.types import Chunk


class CombiningMarkIdentifierTests(unittest.TestCase):
    def test_arabic_diacritics_stay_with_identifiers(self):
        word = "كَتَبَ"
        self.assertEqual(tokenize(word), (word,))
        self.assertEqual(retrieval_query_terms(word), (word,))

    def test_devanagari_combining_marks_stay_with_identifiers(self):
        word = "नमस्ते"
        self.assertEqual(tokenize(word), (word,))
        self.assertEqual(retrieval_query_terms(word), (word,))

    def test_rank_search_finds_complete_marked_identifier(self):
        symbol = "नमस्ते"
        docs = [
            Chunk("a.py", 1, 1, f"{symbol} = 1"),
            Chunk("b.py", 1, 1, "नमस त = 1"),
        ]
        results = rank_chunks(docs, symbol)
        self.assertTrue(results)
        self.assertEqual(results[0].chunk.path, "a.py")

    def test_ascii_snake_and_camel_behavior_remains(self):
        tokens = tokenize("parseURL user_ID")
        self.assertIn("parseurl", tokens)
        self.assertIn("parse", tokens)
        self.assertIn("url", tokens)
        self.assertIn("user_id", tokens)
        self.assertIn("user", tokens)
        self.assertIn("id", tokens)


if __name__ == "__main__":
    unittest.main()
