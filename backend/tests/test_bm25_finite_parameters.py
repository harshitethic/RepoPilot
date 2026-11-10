import unittest
from services.rag.bm25 import BM25
from services.rag.types import Chunk
class FiniteParameters(unittest.TestCase):
    def test_nonfinite_k1_is_rejected(self):
        for value in (float('nan'),float('inf'),float('-inf')):
            with self.assertRaises(ValueError): BM25([Chunk('a.py',1,1,'needle')],k1=value)
        self.assertGreater(BM25([Chunk('a.py',1,1,'needle')]).scores('needle')[0],0)
