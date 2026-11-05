"""Evaluate the first source file selected by Ask AI on the fictional catalog."""
import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from create_demo_zip import DEMO_FILES
from services.analyzer import build_context


# Evidence strings distinguish a definition from an import of the same symbol.
CASES = [
    ("Where is find_title defined?", "src/catalog.py", "def find_title("),
    ("Where is test_query defined?", "tests/test_catalog.py", "def test_query("),
    ("catalog_handler", "src/api.py", "def catalog_handler("),
    ("Which Python version does the project require?", "pyproject.toml", "requires-python"),
    ("Where is SKU looked up?", "src/catalog.py", 'product.get("sku")'),
]


def evaluate(root):
    results = []
    for question, expected, evidence in CASES:
        context = build_context(root, question, max_files=1)
        header, _, excerpt = context.lstrip("\n").partition("\n")
        selected = header[10:-4] if header.startswith("--- FILE: ") and header.endswith(" ---") else None
        results.append({
            "question": question, "expected": expected, "selected": selected,
            "passed": selected == expected and evidence in excerpt,
        })
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print machine-readable case results")
    args = parser.parse_args()
    with TemporaryDirectory() as directory:
        root = Path(directory)
        for name, contents in DEMO_FILES.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents, encoding="utf-8")
        results = evaluate(root)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for row in results:
            status = "PASS" if row["passed"] else "FAIL"
            print(f"{status}  {row['question']}  expected={row['expected']}  selected={row['selected']}")
        print(f"{sum(row['passed'] for row in results)}/{len(results)} cases passed")


if __name__ == "__main__":
    main()
