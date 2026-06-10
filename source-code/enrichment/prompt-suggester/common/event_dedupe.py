"""Deduplicate similar key events and search prompts."""
import re
from typing import Any, Dict, List, Set

_STOP = frozenset({
    "the", "and", "for", "with", "near", "along", "from", "that", "this",
    "into", "over", "under", "across", "through", "street", "sidewalk",
    "road", "city", "urban", "video", "clip", "scene",
})


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


def _event_key(ev: Dict[str, Any]) -> tuple:
    return (
        str(ev.get("original_video") or ""),
        round(float(ev.get("segment_start_sec") or 0), 0),
    )


def dedupe_key_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Drop near-duplicate events (same video + time + similar wording)."""
    kept: List[Dict[str, Any]] = []
    for ev in events:
        q = str(ev.get("query_text") or "").strip()
        if not q:
            continue
        duplicate = False
        for existing in kept:
            if _event_key(existing) != _event_key(ev):
                if str(existing.get("original_video")) != str(ev.get("original_video")):
                    continue
                start_a = float(existing.get("segment_start_sec") or 0)
                start_b = float(ev.get("segment_start_sec") or 0)
                if abs(start_a - start_b) > 12:
                    continue
            label_a = str(existing.get("label") or existing.get("query_text") or "")
            label_b = str(ev.get("label") or q)
            if similar_text(q, str(existing.get("query_text") or "")) or similar_text(
                label_a, label_b
            ):
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


def normalize_search_prompt(text: str, max_words: int = 6) -> str:
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


_GENERIC_PROMPT = re.compile(
    r"^(?:a |an )?(?:busy|bustling|moderately|sunny|urban|city)\s+",
    re.IGNORECASE,
)


def dedupe_prompts(prompts: List[str]) -> List[str]:
    kept: List[str] = []
    for p in prompts:
        q = normalize_search_prompt(p)
        if not q or len(q) < 8 or _GENERIC_PROMPT.match(q):
            continue
        if any(similar_text(q, k) for k in kept):
            continue
        kept.append(q)
    return kept
