import tempfile
import unittest
from pathlib import Path

from services.analyzer import analyze, search_code


class ModernModuleAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_module_files_are_indexed_and_searchable(self):
        files = {
            "src/entry.mjs": ("JavaScript", "needleEsm"),
            "src/worker.cjs": ("JavaScript", "needleCjs"),
            "src/feature.mts": ("TypeScript", "needleMts"),
            "src/config.cts": ("TypeScript", "needleCts"),
        }
        for name, (_, symbol) in files.items():
            self.write(name, f"export const {symbol} = true;")
        result = analyze(self.root)
        self.assertEqual(result["file_count"], 4)
        self.assertEqual(
            {item["name"]: item["files"] for item in result["languages"]},
            {"JavaScript": 2, "TypeScript": 2},
        )
        for name, (_, symbol) in files.items():
            with self.subTest(name=name):
                matches = search_code(self.root, symbol)
                self.assertEqual([(row["path"], row["line"]) for row in matches], [(name, 1)])

    def test_modern_test_filename_variants_are_detected(self):
        variants = (
            "widget.test.jsx", "widget.spec.jsx",
            "widget.test.mjs", "widget.spec.mjs",
            "widget.test.cjs", "widget.spec.cjs",
            "widget.test.mts", "widget.spec.mts",
            "widget.test.cts", "widget.spec.cts",
        )
        for name in variants:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                (Path(directory) / name).write_text("test('works', () => {});", encoding="utf-8")
                report = analyze(Path(directory))
                self.assertTrue(report["signals"]["tests"], name)
                self.assertNotIn("No tests detected", report["warnings"])

    def test_regular_module_does_not_imply_tests(self):
        self.write("src/index.mjs", "export const x = 1;")
        self.assertFalse(analyze(self.root)["signals"]["tests"])


if __name__ == "__main__":
    unittest.main()
