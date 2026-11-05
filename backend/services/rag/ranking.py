"""Rank BM25 evidence, add source-level signals, and diversify results."""
from .bm25 import BM25
from .diversity import select_diverse
from .signals import lexical_boost
from .tokenize import distinct_query_terms
from .types import Chunk, Hit


def rank_chunks(chunks: list[Chunk], query: str, *, limit: int = 8) -> list[Hit]:
    if not 1 <= limit <= 20:
        raise ValueError("limit must be between 1 and 20")
    if not distinct_query_terms(query):
        return []
    weights = BM25(chunks).scores(query)
    candidates = [
        Hit(chunk, score + lexical_boost(chunk, query))
        for chunk, score in zip(chunks, weights)
        if score > 0 or query.casefold().strip() in chunk.path.casefold()
    ]
    candidates.sort(
        key=lambda hit: (
            -hit.score, hit.chunk.path.casefold(),
            hit.chunk.start_line,
        )
    )
    return select_diverse(candidates[: max(40, limit * 5)], limit=limit)
