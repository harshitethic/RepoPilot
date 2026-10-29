import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from services import github
from services import analyzer

class Regression(unittest.TestCase):
    def test_language_ties_use_alphabetic_order(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            files=[root/"z.py",root/"a.ts",root/"b.js"]
            for path in files:path.write_text("x=1")
            with patch.object(analyzer,"iter_files",return_value=files):
                first=analyzer.analyze(root)["languages"]
            with patch.object(analyzer,"iter_files",return_value=list(reversed(files))):
                second=analyzer.analyze(root)["languages"]
            self.assertEqual(first,second)
            self.assertEqual([x["name"] for x in first],["JavaScript","Python","TypeScript"])


if __name__ == "__main__": unittest.main()
