"""Definition questions should locate JS/TS declarations, not import sites."""
import tempfile
import unittest
from pathlib import Path

from services.analyzer import build_context


class JavaScriptDefinitionLookupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_exported_async_function_outscores_import_and_readme(self):
        self.write("README.md", "The processBatch helper is documented here.")
        self.write("app.ts", "import { processBatch } from './batch';")
        self.write("batch.ts", "export async function processBatch(items: string[]) { return items; }")
        result = build_context(self.root, "Where is processBatch defined?", max_files=1)
        self.assertIn("--- FILE: batch.ts ---", result)
        self.assertIn("export async function processBatch", result)
        self.assertNotIn("--- FILE: app.ts ---", result)

    def test_default_exported_class_and_interface_rank_first(self):
        self.write("README.md", "WidgetController is a class and a helper.")
        self.write("app.tsx", "import { WidgetController } from './widgets';")
        self.write("widgets.tsx", "export default class WidgetController {}")
        result = build_context(self.root, "Where is WidgetController declared?", max_files=1)
        self.assertIn("--- FILE: widgets.tsx ---", result)
        self.assertIn("class WidgetController", result)
        self.write("types.ts", "export interface WidgetConfig { enabled: boolean }")
        self.write("README.md", "WidgetConfig is needed by the application.")
        types = build_context(self.root, "Where is WidgetConfig defined?", max_files=1)
        self.assertIn("--- FILE: types.ts ---", types)

    def test_arrow_function_const_in_mjs_outscores_use_site(self):
        self.write("main.mjs", "renderPanel()")
        self.write("ui/panel.mjs", "export const renderPanel = () => 'ok';")
        result = build_context(self.root, "Where is renderPanel defined?", max_files=1)
        self.assertIn("--- FILE: ui/panel.mjs ---", result)

    def test_similar_identifier_does_not_claim_an_exact_definition(self):
        self.write("app.ts", "const loadDataLater = () => {};")
        self.write("real.ts", "export function loadData() {}")
        result = build_context(self.root, "Where is loadData defined?", max_files=1)
        self.assertIn("--- FILE: real.ts ---", result)
        self.assertNotIn("--- FILE: app.ts ---", result)


if __name__ == "__main__":
    unittest.main()
