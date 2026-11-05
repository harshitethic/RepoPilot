"""Repository-scoped lexical retrieval with no network calls or paid models."""
from pathlib import Path

from .corpus import scan_corpus
from .ranking import rank_chunks
from .types import Hit


def retrieve(
    root: Path,
    question: str,
    *,
    limit: int = 8,
    path_prefix: str | None = None,
) -> list[Hit]:
    if not question.strip() or len(question) > 1200:
        raise ValueError("Question must be between 1 and 1200 characters")
    if not 1 <= limit <= 20:
        raise ValueError("limit must be between 1 and 20")
    corpus = scan_corpus(root, path_prefix=path_prefix)
    return rank_chunks(corpus, question, limit=limit)
