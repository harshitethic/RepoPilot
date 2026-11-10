import unittest
from services.rag.tokenize import retrieval_query_terms
from services.rag.ranking import rank_chunks
from services.rag.types import Chunk
class CamelAtomic(unittest.TestCase):
    def test_unknown_camel_symbol_does_not_match_component_words(self):
        self.assertEqual(retrieval_query_terms('unknownAuthToken'),('unknownauthtoken',))
        self.assertEqual(rank_chunks([Chunk('auth.py',1,1,'auth token validation')],'unknownAuthToken'),[])
        self.assertTrue(rank_chunks([Chunk('a.py',1,1,'def unknownAuthToken(): pass')],'unknownAuthToken'))
