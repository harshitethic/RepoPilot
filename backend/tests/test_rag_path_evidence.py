import unittest
from services.rag.ranking import rank_chunks
from services.rag.types import Chunk
class PathEvidence(unittest.TestCase):
    def test_path_is_searchable_without_repeating_it_in_body(self):
        chunks=[Chunk('src/authentication.py',1,1,'def check(): return True'),Chunk('other.py',1,1,'unrelated')]
        self.assertEqual(rank_chunks(chunks,'authentication')[0].chunk.path,'src/authentication.py')
        self.assertEqual(rank_chunks(chunks,'absent_symbol'),[])
