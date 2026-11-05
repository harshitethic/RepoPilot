"""Pure-Python BM25 relevance scoring for source chunks."""
from collections import Counter
from math import log

from .tokenize import distinct_query_terms, tokenize
from .types import Chunk


class BM25:
    def __init__(self, chunks: list[Chunk], *, k1: float = 1.2, b: float = 0.75):
        if k1 <= 0 or not 0 <= b <= 1:
            raise ValueError("Invalid BM25 parameters")
        self.lengths: list[int] = []
        self.counts: list[Counter[str]] = []
        self.frequency: Counter[str] = Counter()
        self.k1 = k1
        self.b = b
        for chunk in chunks:
            count = Counter(tokenize(chunk.text))
            self.counts.append(count)
            self.lengths.append(sum(count.values()))
            self.frequency.update(count.keys())
        self.total = len(chunks)
        self.avg_length = (sum(self.lengths) / self.total) if self.total else 0

    def scores(self, query: str) -> list[float]:
        if not self.total:
            return []
        scores = [0.0] * self.total
        for term in distinct_query_terms(query):
            df = self.frequency.get(term, 0)
            if not df:
                continue
            idf = log(1 + (self.total - df + 0.5) / (df + 0.5))
            for i, terms in enumerate(self.counts):
                freq = terms.get(term, 0)
                if not freq:
                    continue
                norm = 1 - self.b + self.b * (self.lengths[i] / max(1, self.avg_length))
                scores[i] += idf * freq * (self.k1 + 1) / (freq + self.k1 * norm)
        return scores
