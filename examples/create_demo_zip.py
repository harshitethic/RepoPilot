"""Deterministic, fictional ZIP data used by the verified browser walkthrough.

No secrets, paid APIs or network calls. Run:
python examples/create_demo_zip.py --output /tmp/fictional-catalog.zip
"""
from __future__ import annotations
import argparse
from pathlib import Path
import zipfile

DEMO_FILES = {'README.md': '# Fictional Catalog Service\n\nOffline demonstration project; no secrets, no network.\n', 'src/catalog.py': '"""A tiny offline catalog used for the public RepoPilot walkthrough."""\ndef find_title(products: list[dict], sku: str) -> str | None:\n    for product in products:\n        if product.get("sku") == sku:\n            return product.get("title")\n    return None\n\ndef search_catalog(products: list[dict], query: str) -> list[dict]:\n    return [p for p in products if query.lower() in p.get("title", "").lower()]\n', 'src/api.py': '"""Simulated app with no imports from external services."""\nfrom .catalog import find_title, search_catalog\n\ndef catalog_handler(products: list[dict], query: str) -> dict:\n    return {"matches": search_catalog(products, query)}\n', 'tests/test_catalog.py': 'from src.catalog import search_catalog\n\ndef test_query():\n    assert search_catalog([{"sku":"1","title":"Notebook"}],"note")\n', 'pyproject.toml': '[project]\nname = "fictional-catalog-service"\nversion = "0.0.1"\nrequires-python = ">=3.11"\n', '.gitignore': '__pycache__/\n*.pyc\n'}

def create_demo_zip(destination: Path) -> Path:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation refuses existing files and symlinks; a first-run demo
    # should never replace another file at a caller-selected output path.
    with destination.open("xb") as output:
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path, contents in DEMO_FILES.items():
                # An explicit DOS timestamp and file mode keep ZIP members
                # reproducible across seconds and independent of host OS.
                member = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
                member.compress_type = zipfile.ZIP_DEFLATED
                member.create_system = 3
                member.external_attr = 0o100644 << 16
                archive.writestr(member, contents)
    return destination

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(create_demo_zip(args.output))
    except FileExistsError:
        parser.error(f"Output already exists: {args.output}. Choose another --output path.")
