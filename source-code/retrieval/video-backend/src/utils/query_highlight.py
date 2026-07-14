"""Query-term extraction and object-aware segment highlighting."""
import re
from typing import Any, List, Optional, Pattern

QUERY_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "to", "of", "in", "on", "at", "by", "for", "with", "from", "as", "into",
    "and", "or", "but", "not", "if", "then", "than", "that", "this", "there",
    "it", "its", "i", "you", "he", "she", "we", "they", "my", "your", "his",
    "next", "near", "beside", "behind", "around", "through", "under", "over",
    "who", "what", "when", "where", "which", "how", "do", "does", "did",
    "has", "have", "had", "can", "could", "would", "should", "will", "shall",
    "only", "just", "also", "still", "even", "very", "more", "most", "some", "any",
})

QUERY_ACTION_WORDS = frozenset({
    "standing", "stand", "sitting", "sit", "walking", "walk", "running", "run",
    "moving", "move", "looking", "look", "holding", "hold", "wearing", "wear",
    "talking", "talk", "playing", "play", "dancing", "dance", "jumping", "jump",
    "lying", "lie", "lay", "eating", "eat", "drinking", "drink", "driving", "drive",
})

TOKEN_RE = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)*", re.IGNORECASE)


def _tokenize_query(query_text: str) -> List[str]:
    return [match.group(0).lower() for match in TOKEN_RE.finditer(query_text or "")]


def _build_content_phrases(tokens: List[str], skip: frozenset) -> List[str]:
    phrases: List[str] = []
    current: List[str] = []
    for token in tokens:
        if token in skip or len(token) < 2:
            if current:
                phrases.append(" ".join(current))
                current = []
            continue
        current.append(token)
    if current:
        phrases.append(" ".join(current))
    return phrases


def extract_highlight_terms(query_text: str) -> List[str]:
    """Content phrases from query (stop/action words removed), longest first."""
    if not query_text or not query_text.strip():
        return []

    skip = QUERY_STOP_WORDS | QUERY_ACTION_WORDS
    phrases = _build_content_phrases(_tokenize_query(query_text), skip)

    terms: set[str] = set(phrases)
    for phrase in phrases:
        if " " in phrase:
            for part in phrase.split():
                if "-" in part or "'" in part:
                    terms.add(part)

    return sorted(terms, key=lambda item: (-len(item), item))


def _part_to_pattern(part: str) -> str:
    if "-" in part or "'" in part:
        segments = [re.escape(segment) for segment in re.split(r"[-']", part) if segment]
        return r"[-\s]?".join(segments)
    return re.escape(part)


def build_term_pattern(term: str) -> Pattern[str]:
    parts = [part for part in term.strip().split() if part]
    if not parts:
        return re.compile(r"(?!x)x")
    body = r"[-\s]+".join(_part_to_pattern(part) for part in parts)
    return re.compile(rf"(?<!\w)({body})(?!\w)", re.IGNORECASE)


def term_in_text(term: str, text: str) -> bool:
    if not term or not text:
        return False
    return bool(build_term_pattern(term).search(text))


def term_matches_label(term: str, label: str) -> bool:
    if not term or not label:
        return False
    return term_in_text(term.strip(), label.strip())


def object_class_labels(segment: dict) -> List[str]:
    labels: List[str] = []
    object_classes = str(segment.get("object_classes") or "")
    if object_classes.strip():
        labels.extend(part.strip() for part in re.split(r"[,;|]", object_classes) if part.strip())
    return labels


def _reasoning_text(segment: Any) -> str:
    if isinstance(segment, dict):
        return str(segment.get("reasoning_content") or "").strip()
    return str(getattr(segment, "reasoning_content", None) or "").strip()


def segment_query_term_score(segment: dict, highlight_terms: List[str]) -> int:
    blob = _reasoning_text(segment)
    if not blob:
        return 0
    return sum(1 for term in highlight_terms if term_in_text(term, blob))


def timeline_query_term_score(segment: Any, highlight_terms: List[str]) -> int:
    blob = _reasoning_text(segment)
    if not blob:
        return 0
    return sum(1 for term in highlight_terms if term_in_text(term, blob))


def segment_query_highlight(segment: dict, highlight_terms: List[str]) -> bool:
    """True when query content terms match object_classes or reasoning text."""
    if not highlight_terms:
        return False

    labels = object_class_labels(segment)
    for term in highlight_terms:
        for label in labels:
            if term_matches_label(term, label):
                return True

    blob = _reasoning_text(segment)
    if not blob:
        return False
    return any(term_in_text(term, blob) for term in highlight_terms)
