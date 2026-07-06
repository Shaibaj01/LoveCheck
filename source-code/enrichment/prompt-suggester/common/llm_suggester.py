"""Generate search prompts and key events from sampled segments."""
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
from opentelemetry import trace

from .event_dedupe import dedupe_key_events, dedupe_prompts
from .models import KeyEventSuggestion, Settings
from .stream_index import stream_fields_from_row, timeline_sec

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

SYSTEM_PROMPT = """You help operators search a NYC street-safety video index.
Output JSON only.

Input: SAMPLE SEGMENTS — sparse clip captions from recent videos.

Goals:
1) search_prompts: exactly {search_count} SHORT search-box queries (not captions).
   - At most 6 words. One line. No period. No commas.
   - Each prompt MUST use a DIFFERENT primary subject (vehicle type, person role, hazard, brand).
   - Lead with subject + ACTION (blocking, turning, crossing, delivering, near-miss, conflict).
   - NEVER repeat the same subject with only a different landmark ("food trucks near X" is banned).
   - At most ONE food truck/cart/vendor prompt in the whole list. At most ONE taxi/cab prompt.
   - Do NOT use idle scenes: waiting at crosswalk, passing taxi, parked vehicles, "near sign/hydrant".
   - Do NOT add filler: urban setting, daylight, clear skies, no hazards, bustling street.
   - Good: "UPS truck blocking bike lane"
   - Good: "Cyclist swerving around open door"
   - Bad: "Food trucks near traffic lights" / "Pedestrians waiting at crosswalk"

2) key_events: up to {events_count} UNIQUE investigative moments across ALL videos.
   - Max {max_per_video} key_events per video unless severity is high.
   - Same diversity rules as search_prompts — no landmark-only duplicates.
   - SKIP idle parked vehicles, waiting pedestrians, generic "near landmark" lines.
   - Prefer: conflicts, blocking, deliveries, jaywalking, construction hazards, brands, near-misses.
   - label: 3–8 word headline, Title Case, MUST differ from query_text.
   - query_text: SHORT search phrase — max 6 words, subject + action (not "X near Y").

Keep JSON compact. No markdown. Close all brackets.
Schema:
{{"search_prompts":["..."],"key_events":[{{"query_text":"...","label":"...","original_video":"...","filename":"...","segment_start_sec":0,"segment_end_sec":5}}]}}
"""


def _video_meta(row: dict) -> Tuple[str, str]:
    ov = str(row.get("original_video") or row.get("source") or "").strip()
    fn = str(row.get("filename") or ov.rsplit("/", 1)[-1])
    return ov, fn


def _corpus_object_hints(segments: List[dict], limit: int = 14) -> str:
    from collections import Counter

    counts: Counter = Counter()
    for seg in segments:
        raw = str(seg.get("object_classes") or "")
        for part in re.split(r"[,;|]", raw):
            name = part.strip().lower()
            if name and name not in ("person", "car"):
                counts[name] += 1
    if not counts:
        return ""
    top = ", ".join(k for k, _ in counts.most_common(limit))
    return f"Distinct objects in corpus (spread prompts across these; do not repeat one type): {top}\n\n"


def _format_corpus(segments: List[dict], max_segment_lines: int) -> str:
    parts: List[str] = ["=== SAMPLE SEGMENTS ==="]
    for seg in segments[:max_segment_lines]:
        ov, fn = _video_meta(seg)
        sn = int(seg.get("segment_number") or 0)
        start = float(seg.get("segment_start_sec") or 0)
        end = float(seg.get("segment_end_sec") or start + 5)
        cap = str(seg.get("dense_caption") or seg.get("reasoning_content") or "")[:350]
        objs = str(seg.get("object_classes") or "")
        stream = stream_fields_from_row(seg)
        stream_note = ""
        if stream.get("stream_id") is not None:
            stream_note = (
                f" | stream chunk={stream.get('chunk_index', '?')}"
                f" @ {timeline_sec(seg):.0f}s"
            )
        parts.append(
            f"- video={ov} | file={fn} | seg={sn} | {start:.0f}-{end:.0f}s"
            f"{stream_note} | objects={objs} | {cap}"
        )
    return "\n".join(parts)


def _extract_json_block(text: str) -> str:
    cleaned = text.strip()
    if "```" in cleaned:
        match = re.search(r"```(?:json)?\s*(\{.*)", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1)
    start = cleaned.find("{")
    if start < 0:
        return cleaned
    return cleaned[start:]


def _repair_json(text: str) -> str:
    s = text.strip()
    s = re.sub(r",\s*]", "]", s)
    s = re.sub(r",\s*}", "}", s)
    if s.count("[") > s.count("]"):
        s += "]" * (s.count("[") - s.count("]"))
    if s.count("{") > s.count("}"):
        s += "}" * (s.count("{") - s.count("}"))
    return s


def _salvage_prompts(text: str) -> List[str]:
    block = re.search(r'"search_prompts"\s*:\s*\[(.*?)\]', text, re.DOTALL)
    if not block:
        return []
    return [m.group(1).replace('\\"', '"') for m in re.finditer(r'"((?:[^"\\]|\\.)*)"', block.group(1))]


def _salvage_key_events(text: str) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    pattern = (
        r'\{\s*"query_text"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*"label"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,'
        r'\s*"original_video"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*"filename"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,'
        r'\s*"segment_start_sec"\s*:\s*([\d.]+)\s*,\s*"segment_end_sec"\s*:\s*([\d.]+)\s*\}'
    )
    for m in re.finditer(pattern, text):
        events.append({
            "query_text": m.group(1).replace('\\"', '"'),
            "label": m.group(2).replace('\\"', '"'),
            "original_video": m.group(3).replace('\\"', '"'),
            "filename": m.group(4).replace('\\"', '"'),
            "segment_start_sec": float(m.group(5)),
            "segment_end_sec": float(m.group(6)),
        })
    return events


def _parse_llm_json(content: str) -> Dict[str, Any]:
    block = _extract_json_block(content)
    attempts = [block, _repair_json(block)]
    end = block.rfind("}")
    if end > 0:
        attempts.append(_repair_json(block[: end + 1]))

    last_err: Optional[Exception] = None
    for candidate in attempts:
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError as exc:
            last_err = exc

    logger.warning(
        "[SUGGEST] JSON parse failed (%s); salvaging partial LLM output",
        last_err,
    )
    return {
        "search_prompts": _salvage_prompts(content),
        "key_events": _salvage_key_events(content),
    }


def _new_batch_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:8]


def _normalize_key_event(ev: KeyEventSuggestion) -> KeyEventSuggestion:
    from .event_dedupe import normalize_search_prompt

    q = normalize_search_prompt(ev.query_text.strip(), max_words=8) or ev.query_text.strip()[:80]
    lbl = (ev.label or "").strip()
    if not lbl or lbl.lower() == q.lower():
        lbl = ""
    if len(lbl) > 80:
        lbl = " ".join(lbl.split()[:8])
    return ev.model_copy(
        update={
            "query_text": q,
            "label": lbl,
            "original_video": (ev.original_video or "").strip(),
            "filename": (ev.filename or "").strip(),
        }
    )


def _enrich_events_from_segments(
    events: List[Dict[str, Any]],
    segments: List[dict],
) -> List[Dict[str, Any]]:
    """Attach original_video/filename from corpus when the LLM omits them."""
    from .event_dedupe import similar_text

    enriched: List[Dict[str, Any]] = []
    for ev in events:
        ov = str(ev.get("original_video") or "").strip()
        if ov:
            if not str(ev.get("filename") or "").strip():
                for seg in segments:
                    seg_ov, seg_fn = _video_meta(seg)
                    if seg_ov == ov:
                        ev = {**ev, "filename": seg_fn}
                        break
            enriched.append(ev)
            continue

        needle = str(ev.get("label") or ev.get("query_text") or "").strip()
        if not needle:
            continue
        start = float(ev.get("segment_start_sec") or 0)
        best_seg: Optional[dict] = None
        best_score = 0.0
        for seg in segments:
            seg_start = float(seg.get("segment_start_sec") or 0)
            if abs(seg_start - start) > 10:
                continue
            cap = str(seg.get("dense_caption") or seg.get("reasoning_content") or "")
            if similar_text(needle, cap, threshold=0.28):
                score = len(_tokens_overlap(needle, cap))
                if score > best_score:
                    best_score = score
                    best_seg = seg
        if not best_seg:
            logger.warning("[SUGGEST] Dropping key_event without video: %s", needle[:72])
            continue
        seg_ov, seg_fn = _video_meta(best_seg)
        enriched.append({
            **ev,
            "original_video": seg_ov,
            "filename": seg_fn,
            "segment_start_sec": float(best_seg.get("segment_start_sec") or start),
            "segment_end_sec": float(
                best_seg.get("segment_end_sec") or float(best_seg.get("segment_start_sec") or start) + 5
            ),
        })
    return enriched


def _tokens_overlap(a: str, b: str) -> set:
    from .event_dedupe import _tokens
    return _tokens(a) & _tokens(b)


def generate_suggestions(
    settings: Settings,
    segments: List[dict],
) -> Tuple[List[str], List[Dict[str, Any]], str]:
    """Call Cosmos; dedupe LLM key events."""
    if not segments:
        return [], [], ""

    batch_id = _new_batch_id()
    segment_lines = min(settings.suggestions_max_segments, 48)
    corpus = _format_corpus(segments, segment_lines)
    max_per_video = getattr(settings, "suggestions_max_events_per_video", 3)
    event_target = settings.suggestions_events_count
    if len(segments) > 80:
        event_target = min(event_target, 18)

    system = SYSTEM_PROMPT.format(
        search_count=settings.suggestions_search_count,
        events_count=event_target,
        max_per_video=max_per_video,
    )
    user = (
        f"Corpus: {len(segments)} sample segments.\n"
        f"{_corpus_object_hints(segments)}{corpus}"
    )

    max_tokens = max(settings.cosmos_max_tokens, 4000)
    payload: Dict[str, Any] = {
        "model": settings.cosmos_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": settings.cosmos_temperature,
        "response_format": {"type": "json_object"},
    }

    with tracer.start_as_current_span("Cosmos Suggestions LLM") as span:
        span.set_attributes({
            "cosmos_url": settings.cosmos_url,
            "model": settings.cosmos_model,
            "segments_sampled": len(segments),
            "max_tokens": max_tokens,
            "event_target": event_target,
        })
        response = requests.post(settings.cosmos_url, json=payload, timeout=180)
        if response.status_code == 400 and "response_format" in (response.text or ""):
            payload.pop("response_format", None)
            response = requests.post(settings.cosmos_url, json=payload, timeout=180)
        response.raise_for_status()
        body = response.json()

    content = body["choices"][0]["message"]["content"]
    finish = (body.get("choices") or [{}])[0].get("finish_reason")
    if finish == "length":
        logger.warning("[SUGGEST] LLM hit max_tokens=%s; using salvage/repair", max_tokens)

    data = _parse_llm_json(content)

    prompts = dedupe_prompts([
        str(p).strip() for p in data.get("search_prompts", []) if str(p).strip()
    ], limit=settings.suggestions_search_count)

    llm_events: List[Dict[str, Any]] = []
    for ev in data.get("key_events", []):
        if not isinstance(ev, dict) or not ev.get("query_text"):
            continue
        normalized = _normalize_key_event(KeyEventSuggestion.model_validate(ev))
        llm_events.append(normalized.model_dump())

    llm_events = _enrich_events_from_segments(llm_events, segments)
    events = dedupe_key_events(llm_events)
    events.sort(
        key=lambda e: (
            float(e.get("stream_position_sec") or e.get("segment_start_sec") or 0),
            str(e.get("original_video") or ""),
        )
    )
    events = events[: settings.suggestions_events_count]

    return prompts, events, batch_id
