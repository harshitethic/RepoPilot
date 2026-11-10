import unittest
from services.rag.chunk import chunk_source
from services.analyzer import search_code
from pathlib import Path
import tempfile
class PhysicalSourceLines(unittest.TestCase):
    def test_unicode_separators_do_not_shift_citations(self):
        text='value = "a\u2028b"\nneedle = 1\n'
        chunk=list(chunk_source('a.py',text))[0]
        self.assertEqual(chunk.end_line,2)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'a.py').write_text(text)
            self.assertEqual(search_code(root,'needle')[0]['line'],2)
    def test_crlf_and_blank_final_lines(self):
        self.assertEqual(list(chunk_source('a.py','a\r\nb\r\n'))[0].end_line,2)
