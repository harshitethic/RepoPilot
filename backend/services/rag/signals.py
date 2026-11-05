"""Explainable boosts for exact source symbols and path matches."""
from .tokenize import distinct_query_terms
from .types import Chunk


def lexical_boost(chunk: Chunk, query: str) -> float:
    terms = distinct_query_terms(query)
    if not terms:
        return 0.0
    needle = query.casefold().strip()
    body = chunk.text.casefold()
    path = chunk.path.casefold()
    boost = 0.0
    if len(needle) > 2 and needle in body:
        boost += 1.5
    if needle and needle in path:
        boost += 1.8
    path_words = set(distinct_query_terms(path))
    boost += 0.35 * sum(term in path_words for term in terms)
    if path.endswith((".py", ".ts", ".tsx", ".js", ".go", ".rs")):
        boost += 0.05
    return boost
