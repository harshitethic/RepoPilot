"""Maximum marginal relevance to avoid near-duplicate RAG evidence."""
from .tokenize import tokenize
from .types import Hit


def _similarity(left: Hit, right: Hit) -> float:
    if left.chunk.path == right.chunk.path:
        same_file = 0.3
    else:
        same_file = 0
    a = set(tokenize(left.chunk.text))
    b = set(tokenize(right.chunk.text))
    if not a or not b:
        return same_file
    return min(1.0, same_file + (len(a & b) / len(a | b)))


def select_diverse(hits: list[Hit], *, limit: int, relevance_weight: float = 0.75) -> list[Hit]:
    if limit < 1 or not 0 <= relevance_weight <= 1:
        raise ValueError("Invalid diversity settings")
    if not hits:
        return []
    # Repeated corpus entries must not consume separate citation slots.
    unique = {}
    for hit in hits:
        key = (hit.chunk.path, hit.chunk.start_line, hit.chunk.end_line, hit.chunk.text)
        if key not in unique or hit.score > unique[key].score:
            unique[key] = hit
    candidates = list(unique.values())
    selected: list[Hit] = []
    normalizer = max(h.score for h in candidates) or 1.0
    while candidates and len(selected) < limit:
        best_index = max(
            range(len(candidates)),
            key=lambda i: (
                relevance_weight * (candidates[i].score / normalizer)
                - (1 - relevance_weight) * max(
                    (_similarity(candidates[i], picked) for picked in selected),
                    default=0,
                ),
                candidates[i].score,
                -i,
            ),
        )
        selected.append(candidates.pop(best_index))
    return selected
