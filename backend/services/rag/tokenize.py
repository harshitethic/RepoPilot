"""Dependency-free, Unicode-aware source and query tokenization."""
import re

_IDENTIFIER = re.compile(r"(?u)[^\W_]+(?:_[^\W_]+)*")
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def tokenize(text: str) -> tuple[str, ...]:
    """Keep complete source symbols and their constituent words.

    Preserve short symbols (e.g. C, R) used in source code. Casefolding
    supports Unicode identifiers without relying on locale configuration.
    """
    words: list[str] = []
    for match in _IDENTIFIER.finditer(text):
        raw = match.group()
        full = raw.casefold()
        words.append(full)
        parts = []
        for segment in raw.split("_"):
            parts.extend(part.casefold() for part in _CAMEL.split(segment) if part)
        if len(parts) > 1:
            words.extend(parts)
    return tuple(words)


def distinct_query_terms(text: str, maximum: int = 32) -> tuple[str, ...]:
    """Cap query expansion before scoring imported repositories."""
    if maximum < 1:
        raise ValueError("maximum must be positive")
    return tuple(dict.fromkeys(tokenize(text)))[:maximum]
