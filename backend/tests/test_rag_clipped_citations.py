import unittest
from services.rag.context import prepare_evidence, references
from services.rag.types import Chunk, Hit
class ClippedCitations(unittest.TestCase):
    def test_citation_range_tracks_visible_excerpt(self):
        hit=Hit(Chunk('a.py',10,99,'line content\n'*90),1)
        text,included=prepare_evidence([hit],char_budget=240)
        self.assertTrue(included)
        self.assertLess(included[0].chunk.end_line,99)
        self.assertIn(references(included)[0]['citation'],text)
        self.assertLessEqual(len(text),240)
    def test_visible_blank_lines_keep_their_line_range(self):
        hit=Hit(Chunk('a.py',10,12,'value\n\n\n'),1)
        _,included=prepare_evidence([hit])
        self.assertEqual(included[0].chunk.end_line,12)
