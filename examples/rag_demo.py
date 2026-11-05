"""A truthful offline RAG example over disposable repository source files."""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from services.rag.service import retrieve  # noqa: E402


def main():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        (root / "payments.py").write_text(
            "def refund_payment(payment_id):\n"
            "    # Undo a captured payment\n"
            "    return payment_id\n",
            encoding="utf-8",
        )
        (root / "readme.md").write_text(
            "This fictional example shows refund handling.\n",
            encoding="utf-8",
        )
        results = retrieve(root, "refund_payment")
        for hit in results:
            print(f"{hit.chunk.citation} (score {hit.score:.2f})")
        if not results or results[0].chunk.path != "payments.py":
            raise SystemExit("Retrieval verification failed")
        print("Verified: offline, actual source file, no model call")


if __name__ == "__main__":
    main()
