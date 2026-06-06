"""Shared text utilities for deterministic retrieval, extraction, and evaluation."""

import re
from collections import Counter
from collections.abc import Iterable

TOKEN_RE = re.compile(r"[a-z][a-z0-9-]{2,}")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")

STOPWORDS = {
    "about",
    "after",
    "also",
    "and",
    "are",
    "because",
    "before",
    "between",
    "from",
    "have",
    "into",
    "that",
    "the",
    "their",
    "them",
    "then",
    "there",
    "these",
    "this",
    "those",
    "when",
    "where",
    "which",
    "while",
    "with",
    "would",
    "could",
    "should",
    "does",
    "did",
    "how",
    "why",
    "what",
    "were",
    "was",
    "for",
    "not",
    "but",
    "can",
    "has",
    "had",
}


def tokenize(text: str) -> list[str]:
    """Return normalized content tokens with common question words removed."""
    return [token for token in TOKEN_RE.findall(text.lower()) if token not in STOPWORDS]


def token_set(text: str) -> set[str]:
    """Return a deduplicated set of normalized content tokens."""
    return set(tokenize(text))


def overlap_terms(left: Iterable[str], right: Iterable[str]) -> list[str]:
    """Return sorted tokens that appear in both iterables."""
    return sorted(set(left).intersection(right))


def important_terms(text: str, limit: int = 8) -> list[str]:
    """Return the highest-frequency content terms in a text."""
    counts = Counter(tokenize(text))
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [term for term, _ in ranked[:limit]]


def noun_phrases(text: str, limit: int = 8) -> list[str]:
    """Extract short deterministic noun-phrase-like spans without external NLP dependencies."""
    phrases: list[str] = []
    for sentence in SENTENCE_RE.split(text.strip()):
        tokens = TOKEN_RE.findall(sentence.lower())
        current: list[str] = []
        for token in tokens:
            if token in STOPWORDS:
                if len(current) >= 2:
                    phrases.append(" ".join(current[:4]))
                current = []
                continue
            current.append(token)
            if len(current) == 4:
                phrases.append(" ".join(current))
                current = current[-1:]
        if len(current) >= 2:
            phrases.append(" ".join(current[:4]))

    seen: set[str] = set()
    unique: list[str] = []
    for phrase in phrases:
        if phrase not in seen:
            seen.add(phrase)
            unique.append(phrase)
        if len(unique) >= limit:
            break
    return unique


def split_sentences(text: str) -> list[str]:
    """Split text into sentence-sized evidence units."""
    return [sentence.strip() for sentence in SENTENCE_RE.split(text.strip()) if sentence.strip()]
