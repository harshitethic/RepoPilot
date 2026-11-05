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


# Generic question scaffolding should not count as relevant source evidence.
# This list deliberately excludes important technical concepts like "auth" or
# "index", which must still be searchable as a user's primary query.
_RETRIEVAL_STOP_WORDS = frozenset({
    "a", "an", "are", "can", "code", "could", "declared", "defined", "did",
    "do", "does", "find", "for", "from", "function", "how", "i", "in",
    "implemented", "implementation", "is", "it", "me", "method", "of",
    "on", "please", "show", "the", "this", "to", "was", "we", "were",
    "what", "where", "which", "who", "why", "would", "you",
})


def retrieval_query_terms(query: str) -> tuple[str, ...]:
    """Use salient terms for retrieval, preserving full snake_case symbols.

    In source-code search, a user-supplied identifier is an atomic target:
    matching an incidental piece of an *unknown* symbol is a false hit.
    Natural-language questions, however, can match source terms individually.
    """
    query = query.strip()
    if "_" in query and query.isidentifier():
        return (query.casefold(),)
    return tuple(
        term for term in distinct_query_terms(query)
        if term not in _RETRIEVAL_STOP_WORDS
    )
