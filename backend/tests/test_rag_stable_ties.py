import unittest
from services.rag.ranking import rank_chunks
from services.rag.types import Chunk
class StableTies(unittest.TestCase):
    def test_case_variant_paths_have_input_independent_order(self):
        chunks=[Chunk('a.py',1,1,'needle'),Chunk('A.py',1,1,'needle')]
        first=[h.chunk.path for h in rank_chunks(chunks,'needle')]
        second=[h.chunk.path for h in rank_chunks(list(reversed(chunks)),'needle')]
        self.assertEqual(first,second)
