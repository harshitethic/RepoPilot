"""The public demonstration fixture is genuine and accepted by the real importer."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from examples.create_demo_zip import DEMO_FILES, create_demo_zip
from services import github
from services.analyzer import analyze, search_code


class BrowserDemoFixtureTests(unittest.TestCase):
    def test_synthetic_repository_is_importable_and_searchable(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            archive = create_demo_zip(directory / "fictional-catalog.zip")
            self.assertEqual(len(DEMO_FILES), 6)
            repos = directory / "imports"
            repos.mkdir()
            with patch.object(github, "BASE_DIR", repos):
                repo_id, repo = github.extract_zip(archive)
                self.assertEqual(repo.name, repo_id)
                result = analyze(repo)
                self.assertEqual(result["file_count"], 6)
                self.assertTrue(any(f["path"] == "src/catalog.py" for f in result["files"]))
                matches = search_code(repo, "search_catalog")
                self.assertTrue(any(r["path"] == "src/catalog.py" for r in matches))
                github.delete_repository(repo_id)
                self.assertFalse(repo.exists())


if __name__ == "__main__":
    unittest.main()
