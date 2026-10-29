import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from services import github
from services import analyzer

class Regression(unittest.TestCase):
    def test_context_finds_symbol_after_prefix(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/"module.py").write_text("x"*5200+"\ndef deep_unique_symbol():\n    return 42\n")
            result=analyzer.build_context(root,"deep_unique_symbol",max_files=1)
            self.assertIn("--- FILE: module.py",result)
            self.assertIn("deep_unique_symbol",result)


if __name__ == "__main__": unittest.main()
