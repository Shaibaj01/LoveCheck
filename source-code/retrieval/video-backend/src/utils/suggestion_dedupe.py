"""Deduplicate suggestions (mirror of prompt-suggester/common/event_dedupe.py)."""
import re
from typing import Any, Dict, List, Optional, Set, Tuple

_STOP = frozenset({
    "the", "and", "for", "with", "near", "along", "from", "that", "this",
    "into", "over", "under", "across", "through", "street", "sidewalk",
    "road", "city", "urban", "video", "clip", "scene", "one", "way", "sign",
})

_NEAR_TAIL = re.compile(
    r"\s+(?:near|by|at|beside|outside|next to|in front of|past|around)\s+.+$",
    re.IGNORECASE,
)

_SUBJECT_BUCKETS: Tuple[Tuple[re.Pattern, str], ...] = (
    (re.compile(r"food\s+(?:truck|cart)|ice\s+cream|hot\s+dog|nathan'?s|vendor", re.I), "food_vendor"),
    (re.compile(r"\b(?:taxi|cab|uber|lyft)\b", re.I), "taxi"),
    (re.compile(r"pedestrian|people\s+waiting|waiting\s+at|crowd\s+at", re.I), "pedestrian_idle"),
    (re.compile(r"crosswalk|traffic\s+light|intersection", re.I), "intersection"),
    (re.compile(r"(?:ups|fedex|usps|delivery)\s+truck|truck\s+block", re.I), "delivery_truck"),
    (re.compile(r"bicycle|cyclist|\bbike\b", re.I), "cyclist"),
    (re.compile(r"construction|scaffold|excavator|forklift", re.I), "construction"),
    (re.compile(r"fire\s+hydrant", re.I), "fire_hydrant"),
)

_LIMIT_ONE_PER_LIST: Set[str] = {
    "food_vendor",
    "taxi",
    "pedestrian_idle",
    "intersection",
    "fire_hydrant",
}

_ACTION_VERB = re.compile(
    r"\b(?:block|turn|cross|deliver|hit|crash|stop|wait|walk|ride|carry|load|unload|"
    r"argue|fall|speed|merge|cut|overtake|unload|park|unload|collid|swerv|brak)\w*\b",
    re.I,
)

_LOW_VALUE = re.compile(
    r"(?:"
    r"pedestrians?\s+waiting|people\s+waiting|waiting\s+at\s+(?:the\s+)?crosswalk|"
    r"(?:yellow\s+)?taxi\s+passing|taxi\s+(?:at|near)\s+|"
    r"(?:food\s+)?(?:truck|cart)s?\s+near|"
    r"food\s+cart\s+with\s+ice\s+cream"
    r")",
    re.I,
)


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


def subject_head(text: str) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip().lower())
    t = _NEAR_TAIL.sub("", t).strip(" ,;:")
    words = [w for w in re.findall(r"[a-z0-9]+", t) if len(w) > 2 and w not in _STOP]
    if not words:
        return t[:40]
    head = " ".join(words[:3])
    if head.endswith("s") and len(head) > 4:
        head = head[:-1]
    return head


def subject_bucket(text: str) -> str:
    t = (text or "").strip().lower()
    for pattern, bucket in _SUBJECT_BUCKETS:
        if pattern.search(t):
            return bucket
    return subject_head(text)


def is_near_landmark_only(text: str) -> bool:
    t = (text or "").strip()
    if not re.search(r"\bnear\b", t, re.I):
        return False
    return _ACTION_VERB.search(t) is None


def prompts_redundant(a: str, b: str) -> bool:
    if similar_text(a, b):
        return True
    bucket_a, bucket_b = subject_bucket(a), subject_bucket(b)
    if bucket_a == bucket_b and bucket_a in _LIMIT_ONE_PER_LIST:
        return True
    head_a, head_b = subject_head(a), subject_head(b)
    if head_a and head_a == head_b:
        return True
    if is_near_landmark_only(a) and is_near_landmark_only(b):
        if head_a == head_b or similar_text(head_a, head_b, threshold=0.66):
            return True
    return False


def is_low_value_prompt(text: str) -> bool:
    t = (text or "").strip()
    if not t or len(t) < 8:
        return True
    if _LOW_VALUE.search(t):
        return True
    if is_near_landmark_only(t):
        return True
    return False


def _event_key(ev: Dict[str, Any]) -> tuple:
    return (
        str(ev.get("original_video") or ""),
        round(float(ev.get("segment_start_sec") or 0), 0),
    )


def dedupe_key_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    global_buckets: Set[str] = set()
    near_only_count = 0

    for ev in events:
        q = str(ev.get("query_text") or "").strip()
        if not q or is_low_value_prompt(q):
            continue

        bucket = subject_bucket(q)
        if bucket in _LIMIT_ONE_PER_LIST and bucket in global_buckets:
            continue
        if is_near_landmark_only(q):
            if near_only_count >= 1:
                continue

        duplicate = False
        for existing in kept:
            same_video = str(existing.get("original_video")) == str(ev.get("original_video"))
            if same_video:
                start_a = float(existing.get("segment_start_sec") or 0)
                start_b = float(ev.get("segment_start_sec") or 0)
                if _event_key(existing) != _event_key(ev) and abs(start_a - start_b) > 12:
                    continue
            else:
                if bucket not in _LIMIT_ONE_PER_LIST:
                    continue

            label_a = str(existing.get("label") or existing.get("query_text") or "")
            label_b = str(ev.get("label") or q)
            if prompts_redundant(q, str(existing.get("query_text") or "")) or similar_text(
                label_a, label_b, threshold=0.58
            ):
                duplicate = True
                break

        if duplicate:
            continue

        kept.append(ev)
        if bucket in _LIMIT_ONE_PER_LIST:
            global_buckets.add(bucket)
        if is_near_landmark_only(q):
            near_only_count += 1

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


def dedupe_prompts(prompts: List[str], limit: Optional[int] = None) -> List[str]:
    kept: List[str] = []
    seen_buckets: Set[str] = set()
    near_only_count = 0

    for p in prompts:
        q = normalize_search_prompt(p)
        if not q or _GENERIC_PROMPT.match(q) or is_low_value_prompt(q):
            continue
        if any(prompts_redundant(q, k) for k in kept):
            continue

        bucket = subject_bucket(q)
        if bucket in _LIMIT_ONE_PER_LIST:
            if bucket in seen_buckets:
                continue
            seen_buckets.add(bucket)

        if is_near_landmark_only(q):
            if near_only_count >= 1:
                continue
            near_only_count += 1

        kept.append(q)
        if limit is not None and len(kept) >= limit:
            break

    return kept
