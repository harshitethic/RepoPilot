import unittest
from services.rag.types import Chunk, Hit
class ExcerptBudget(unittest.TestCase):
    def test_zero_excerpt_does_not_expose_nearly_entire_source(self):
        hit=Hit(Chunk('a.py',1,1,'private source body'),1)
        self.assertEqual(hit.public(0)['text'],'')
        self.assertEqual(hit.public(1)['text'],'…')
        for invalid in (-1,1.5,True):
            with self.assertRaises(ValueError): hit.public(invalid)
