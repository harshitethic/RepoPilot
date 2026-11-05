"""Line-preserving source chunks with deterministic overlap."""
from collections.abc import Iterator

from .types import Chunk


def chunk_source(
    path: str,
    text: str,
    *,
    lines_per_chunk: int = 36,
    overlap_lines: int = 6,
    max_line_chars: int = 2000,
) -> Iterator[Chunk]:
    if lines_per_chunk < 1 or not 0 <= overlap_lines < lines_per_chunk:
        raise ValueError("Invalid chunk size or overlap")
    if max_line_chars < 1:
        raise ValueError("max_line_chars must be positive")
    lines = text.splitlines()
    if not lines:
        return
    stride = lines_per_chunk - overlap_lines
    for offset in range(0, len(lines), stride):
        end = min(offset + lines_per_chunk, len(lines))
        snippet = "\n".join(line[:max_line_chars] for line in lines[offset:end])
        yield Chunk(path, offset + 1, end, snippet)
        if end == len(lines):
            break
