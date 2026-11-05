import tempfile
import unittest
from pathlib import Path

from services.analyzer import analyze, build_context, search_code


class ManifestRetrievalTests(unittest.TestCase):
    def test_go_and_ruby_manifests_are_available_to_repository_tools(self):
        for name, declaration in [
            ("go.mod", "module example.test/sprocket"),
            ("Gemfile", 'gem "sprocket"'),
        ]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / name).write_text(declaration, encoding="utf-8")
                (root / "unrelated.mod").write_bytes(b"unrelated")

                analysis = analyze(root)
                self.assertTrue(analysis["signals"]["manifest"])
                self.assertEqual([row["path"] for row in analysis["files"]], [name])
                self.assertEqual(search_code(root, "sprocket")[0]["text"], declaration)
                self.assertIn(declaration, build_context(root, "sprocket"))
