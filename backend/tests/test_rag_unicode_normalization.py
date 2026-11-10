import unittest
from services.rag.tokenize import tokenize, retrieval_query_terms
from services.rag.ranking import rank_chunks
from services.rag.types import Chunk
class UnicodeNormalization(unittest.TestCase):
    def test_canonically_equivalent_symbols_match(self):
        self.assertEqual(tokenize('cafe\u0301'),tokenize('café'))
        self.assertTrue(rank_chunks([Chunk('a.py',1,1,'café = 1')],'cafe\u0301'))
        self.assertEqual(retrieval_query_terms('cafe\u0301_value'),('café_value',))
