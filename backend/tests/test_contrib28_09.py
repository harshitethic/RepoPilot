import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from services import github
from services import analyzer

class Regression(unittest.TestCase):
    def test_tiny_context_budget_keeps_a_relevant_excerpt(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/"only.py").write_text("needle = 1\n"+"x"*2200)
            result=analyzer.build_context(root,"needle",max_files=1,max_chars=135)
            self.assertIn("--- FILE: only.py",result)
            self.assertIn("needle",result)
            self.assertLessEqual(len(result),135)


if __name__ == "__main__": unittest.main()
