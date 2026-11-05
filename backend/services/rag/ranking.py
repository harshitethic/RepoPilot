"""Rank BM25 evidence, add source-level signals, and diversify results."""
from .bm25 import BM25
from .diversity import select_diverse
from .signals import lexical_boost
from .tokenize import retrieval_query_terms, tokenize
from .types import Chunk, Hit


def rank_chunks(chunks: list[Chunk], query: str, *, limit: int = 8) -> list[Hit]:
    if not 1 <= limit <= 20:
        raise ValueError("limit must be between 1 and 20")
    terms = retrieval_query_terms(query)
    if not terms:
        return []
    weights = BM25(chunks).scores(query)
    # A multi-concept question needs at least two meaningful term matches.
    # One accidental word from a nonexistent identifier is not evidence.
    required_matches = 2 if len(terms) >= 3 else 1
    candidates = []
    for chunk, score in zip(chunks, weights):
        if score <= 0:
            continue
        source_terms = set(tokenize(chunk.path + "\n" + chunk.text))
        if len(source_terms.intersection(terms)) < required_matches:
            continue
        candidates.append(Hit(chunk, score + lexical_boost(chunk, query)))
    candidates.sort(
        key=lambda hit: (
            -hit.score, hit.chunk.path.casefold(),
            hit.chunk.start_line,
        )
    )
    return select_diverse(candidates[: max(40, limit * 5)], limit=limit)
