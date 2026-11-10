"""Typed retrieval records and stable, source-based citations."""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Chunk:
    path: str
    start_line: int
    end_line: int
    text: str

    @property
    def citation(self) -> str:
        return f"{self.path}:L{self.start_line}-L{self.end_line}"


@dataclass(frozen=True, slots=True)
class Hit:
    chunk: Chunk
    score: float

    def public(self, max_excerpt: int = 1800) -> dict:
        if type(max_excerpt) is not int or max_excerpt < 0:
            raise ValueError("max_excerpt must be a non-negative integer")
        text = self.chunk.text
        if max_excerpt == 0:
            text = ""
        if len(text) > max_excerpt:
            text = text[: max_excerpt - 1] + "…"
        return {
            "citation": self.chunk.citation,
            "path": self.chunk.path,
            "start_line": self.chunk.start_line,
            "end_line": self.chunk.end_line,
            "score": round(self.score, 4),
            "text": text,
        }
