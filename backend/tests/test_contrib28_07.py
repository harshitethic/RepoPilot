import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from services import github
from services import analyzer

class Regression(unittest.TestCase):
    def test_nonintegral_search_limits(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/"a.py").write_text("needle")
            for limit in (True,False,1.3,"1",None):
                with self.subTest(limit=limit), self.assertRaises(ValueError):
                    analyzer.search_code(root,"needle",limit=limit)
            self.assertEqual(analyzer.search_code(root,"needle",limit=0),[])


if __name__ == "__main__": unittest.main()
