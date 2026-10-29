import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from services import github
from services import analyzer

class Regression(unittest.TestCase):
    def test_excluded_folders_are_case_insensitive(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for folder in ("NODE_MODULES","VENV",".GIT","__PYCACHE__"):
                p=root/folder/"secret.py"
                p.parent.mkdir(parents=True)
                p.write_text("private marker")
            (root/"main.py").write_text("public marker")
            self.assertEqual([p.name for p in github.iter_files(root)],["main.py"])


if __name__ == "__main__": unittest.main()
