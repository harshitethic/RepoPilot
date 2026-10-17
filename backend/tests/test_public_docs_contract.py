"""Check repo entry-point docs do not link to missing local files."""
import re
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[2]
DOCUMENTS = [
    ROOT / "README.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "docs" / "first-run.md",
]
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


class PublicDocumentationTests(unittest.TestCase):
    def test_first_run_paths_and_local_links_resolve(self):
        for document in DOCUMENTS:
            self.assertTrue(document.is_file())
            for raw in MARKDOWN_LINK.findall(document.read_text(encoding="utf-8")):
                url = urlsplit(raw.strip().split(" ", 1)[0])
                if url.scheme or raw.startswith("//") or raw.startswith("#"):
                    continue
                target = (document.parent / unquote(url.path)).resolve()
                with self.subTest(document=document.name, link=raw):
                    self.assertTrue(
                        target.is_relative_to(ROOT) and target.is_file(),
                        f"Missing or escaped link {raw} in {document.name}",
                    )

    def test_declared_mit_license_exists(self):
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertTrue(license_text.startswith("MIT License\n"))
        self.assertIn("Permission is hereby granted, free of charge", license_text)
        self.assertIn("2026 Harshit Sharma", license_text)


if __name__ == "__main__":
    unittest.main()
