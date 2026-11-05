"""Bounded and deterministic corpus scan using RepoPilot's safe file reader."""
from pathlib import Path

from services.github import iter_files, read_text

from .chunk import chunk_source
from .types import Chunk


def scan_corpus(
    root: Path,
    *,
    max_files: int = 2000,
    max_chunks: int = 4000,
    path_prefix: str | None = None,
) -> list[Chunk]:
    if not 1 <= max_files <= 10000 or not 1 <= max_chunks <= 10000:
        raise ValueError("Invalid corpus budget")
    if path_prefix is not None:
        if (
            not path_prefix
            or path_prefix.startswith(("/", "\\"))
            or "\\" in path_prefix
            or "\x00" in path_prefix
            or any(segment in {".", ".."} for segment in path_prefix.split("/"))
        ):
            raise ValueError("Invalid path prefix")
        path_prefix = path_prefix.rstrip("/")
    chunks: list[Chunk] = []
    file_count = 0
    for source in sorted(iter_files(root), key=lambda p: p.relative_to(root).as_posix()):
        rel = source.relative_to(root).as_posix()
        if path_prefix and rel != path_prefix and not rel.startswith(path_prefix + "/"):
            continue
        if file_count >= max_files or len(chunks) >= max_chunks:
            break
        file_count += 1
        try:
            text = read_text(source)
        except (OSError, UnicodeError):
            continue
        for chunk in chunk_source(rel, text):
            chunks.append(chunk)
            if len(chunks) >= max_chunks:
                break
    return chunks
