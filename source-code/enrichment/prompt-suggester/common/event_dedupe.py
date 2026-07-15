"""Deduplicate grounded search prompts and key events."""
import re
from typing import Any, Dict, List, Optional, Set

_STOP = frozenset({
    "the", "and", "for", "with", "near", "along", "from", "that", "this",
    "into", "over", "under", "across", "through", "video", "clip", "scene",
    "a", "an", "of", "to", "in", "on", "at", "by", "as", "is", "are", "was",
    "were", "be", "been", "being", "it", "its", "or", "but",
})

# Fraction of query content-tokens that must appear in reasoning_content.
_GROUNDING_MIN_OVERLAP = 0.55


def _tokens(text: str) -> Set[str]:
    return {
        w for w in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(w) > 2 and w not in _STOP
    }


def similar_text(a: str, b: str, threshold: float = 0.52) -> bool:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return (a or "").strip().lower() == (b or "").strip().lower()
    overlap = len(ta & tb)
    union = len(ta | tb)
    return overlap / union >= threshold


def grounded_in_reasoning(
    query: str,
    reasoning: str,
    min_overlap: float = _GROUNDING_MIN_OVERLAP,
) -> bool:
    """True when most content tokens in query also appear in reasoning."""
    q = _tokens(query)
    if not q:
        return False
    r = _tokens(reasoning)
    if not r:
        return False
    return (len(q & r) / len(q)) >= min_overlap


def prompts_redundant(a: str, b: str) -> bool:
    return similar_text(a, b, threshold=0.55)


def _event_key(ev: Dict[str, Any]) -> tuple:
    return (
        str(ev.get("original_video") or ""),
        round(float(ev.get("segment_start_sec") or 0), 0),
    )


def dedupe_key_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Drop near-duplicate events (same text or same video+time slot)."""
    kept: List[Dict[str, Any]] = []
    for ev in events:
        q = str(ev.get("query_text") or "").strip()
        if not q or len(q) < 4:
            continue
        duplicate = False
        for existing in kept:
            if _event_key(existing) == _event_key(ev):
                duplicate = True
                break
            if prompts_redundant(q, str(existing.get("query_text") or "")):
                same_video = str(existing.get("original_video")) == str(ev.get("original_video"))
                if same_video:
                    start_a = float(existing.get("segment_start_sec") or 0)
                    start_b = float(ev.get("segment_start_sec") or 0)
                    if abs(start_a - start_b) <= 12:
                        duplicate = True
                        break
                else:
                    duplicate = True
                    break
            label_a = str(existing.get("label") or existing.get("query_text") or "")
            label_b = str(ev.get("label") or q)
            if similar_text(label_a, label_b, threshold=0.7):
                if str(existing.get("original_video")) == str(ev.get("original_video")):
                    duplicate = True
                    break
        if not duplicate:
            kept.append(ev)
    return kept


_PROMPT_FILLER = re.compile(
    r",?\s*(?:"
    r"with no (?:visible )?hazards[^,;]*|"
    r"and no (?:apparent )?hazards[^,;]*|"
    r"under (?:clear )?daylight(?: conditions)?[^,;]*|"
    r"in an? urban (?:setting|environment|area)[^,;]*|"
    r"(?:all )?within an urban environment[^,;]*|"
    r"occurring in the scene|"
    r"visible in the background|"
    r"no (?:unusual|apparent) activity[^,;]*"
    r")",
    re.IGNORECASE,
)


def normalize_search_prompt(text: str, max_words: int = 8) -> str:
    """Short search-box query: trim filler, cap word count."""
    t = re.sub(r"\s+", " ", (text or "").strip().strip('"'))
    t = re.sub(r"^[\d\.\)\-\*]+\s*", "", t)
    if not t:
        return ""
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'(])", t, maxsplit=1)
    t = parts[0].strip().rstrip(".!?")
    for _ in range(6):
        prev = t
        t = _PROMPT_FILLER.sub("", t).strip().rstrip(",;:")
        if t == prev:
            break
    words = t.split()
    if len(words) > max_words:
        t = " ".join(words[:max_words]).rstrip(",;:")
    return t.strip()


def dedupe_prompts(prompts: List[str], limit: Optional[int] = None) -> List[str]:
    kept: List[str] = []
    for p in prompts:
        q = normalize_search_prompt(p)
        if not q or len(q) < 4:
            continue
        if any(prompts_redundant(q, k) for k in kept):
            continue
        kept.append(q)
        if limit is not None and len(kept) >= limit:
            break
    return kept
