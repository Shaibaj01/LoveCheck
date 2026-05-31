"""Query-term extraction and object-aware segment highlighting."""
import json
import re
from typing import Any, Dict, List, Optional, Pattern

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


def parse_structured(vlm_structured: Optional[str]) -> Dict[str, Any]:
    if not vlm_structured or not str(vlm_structured).strip():
        return {}
    raw = str(vlm_structured).strip()
    try:
        data = json.loads(raw)
        if isinstance(data, str):
            data = json.loads(data)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def structured_object_labels(segment: dict) -> List[str]:
    labels: List[str] = []
    structured = parse_structured(segment.get("vlm_structured"))
    for obj in structured.get("objects") or []:
        if isinstance(obj, dict):
            obj_type = str(obj.get("type") or "").strip()
            notes = str(obj.get("notes") or "").strip()
            if obj_type:
                labels.append(obj_type)
            if notes:
                labels.append(notes)
        elif isinstance(obj, str) and obj.strip():
            labels.append(obj.strip())

    object_classes = str(segment.get("object_classes") or "")
    if object_classes.strip():
        labels.extend(part.strip() for part in re.split(r"[,;|]", object_classes) if part.strip())
    return labels


def segment_query_term_score(segment: dict, highlight_terms: List[str]) -> int:
    structured = parse_structured(segment.get("vlm_structured"))
    text_parts = [
        str(structured.get("scene_summary") or ""),
        str(segment.get("dense_caption") or ""),
        str(segment.get("reasoning_content") or ""),
    ]
    blob = " ".join(part for part in text_parts if part).strip()
    if not blob:
        return 0
    return sum(1 for term in highlight_terms if term_in_text(term, blob))


def timeline_query_term_score(segment: Any, highlight_terms: List[str]) -> int:
    blob = " ".join(
        part for part in [
            getattr(segment, "dense_caption", None) or "",
            getattr(segment, "reasoning_content", None) or "",
        ] if part
    ).strip()
    if not blob:
        return 0
    return sum(1 for term in highlight_terms if term_in_text(term, blob))


def segment_query_highlight(segment: dict, highlight_terms: List[str]) -> bool:
    """True when query content terms match structured objects or scene text."""
    if not highlight_terms:
        return False

    labels = structured_object_labels(segment)
    for term in highlight_terms:
        for label in labels:
            if term_matches_label(term, label):
                return True

    structured = parse_structured(segment.get("vlm_structured"))
    text_parts = [
        str(structured.get("scene_summary") or ""),
        str(segment.get("dense_caption") or ""),
        str(segment.get("reasoning_content") or ""),
    ]
    blob = " ".join(part for part in text_parts if part).strip()
    if not blob:
        return False
    return any(term_in_text(term, blob) for term in highlight_terms)
