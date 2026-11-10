import unittest
from services.rag.diversity import select_diverse
from services.rag.types import Chunk, Hit
class DuplicateEvidence(unittest.TestCase):
    def test_duplicate_chunks_do_not_displace_distinct_evidence(self):
        a=Chunk('a.py',1,1,'needle');b=Chunk('b.py',1,1,'other needle')
        result=select_diverse([Hit(a,5),Hit(a,4),Hit(b,1)],limit=2)
        self.assertEqual({h.chunk.path for h in result},{'a.py','b.py'})
        self.assertEqual(result[0].score,5)
