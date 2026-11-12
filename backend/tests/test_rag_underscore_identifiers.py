import unittest

from services.rag.ranking import rank_chunks
from services.rag.tokenize import retrieval_query_terms, tokenize
from services.rag.types import Chunk


class UnderscoreIdentifierTests(unittest.TestCase):
    def test_python_dunder_and_private_names_are_kept_whole(self):
        symbols = ("__init__", "__name__", "_private", "MAX_SIZE_", "two__parts")
        for symbol in symbols:
            with self.subTest(symbol=symbol):
                self.assertIn(symbol.casefold(), tokenize(symbol))
                self.assertEqual(retrieval_query_terms(symbol), (symbol.casefold(),))

    def test_dunder_search_finds_source_exactly(self):
        docs = [
            Chunk("one.py", 1, 1, "def __init__(self): pass"),
            Chunk("other.py", 1, 1, "def init(self): pass"),
        ]
        results = rank_chunks(docs, "__init__")
        self.assertEqual([r.chunk.path for r in results], ["one.py"])

    def test_unicode_name_with_underscores_preserves_marks(self):
        name = "_नमस्ते_"
        self.assertIn(name, tokenize(name))
        self.assertEqual(retrieval_query_terms(name), (name,))

    def test_latin_and_camel_case_remain_searchable(self):
        tokens = tokenize("user_ID getUserName")
        for expected in ("user_id", "user", "id", "getusername", "get", "user", "name"):
            self.assertIn(expected, tokens)

    def test_punctuation_does_not_become_empty_identifiers(self):
        self.assertEqual(tokenize("..--!"), ())


if __name__ == "__main__":
    unittest.main()
