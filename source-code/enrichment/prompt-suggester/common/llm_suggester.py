"""Generate search prompts and key events from rollups + sampled segments."""
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
from opentelemetry import trace

from .event_dedupe import dedupe_key_events, dedupe_prompts
from .models import KeyEventSuggestion, Settings, SuggestionsResult

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

SYSTEM_PROMPT = """You help operators search a NYC street-safety video index.
Output JSON only.

Input sections:
1) VIDEO ROLLUPS — whole-video summaries and timeline events (PREFER for key_events).
2) SAMPLE SEGMENTS — sparse clip captions (use mainly for search_prompts).

Goals:
1) search_prompts: exactly {search_count} distinct semantic-search sentences.
   - Concrete, varied wording from captions/summaries.
   - Not generic ("person on street").

2) key_events: up to {events_count} UNIQUE investigative moments across ALL videos.
   - Use rollup timeline_events when present (convert to query_text + label + timestamps).
   - Max {max_per_video} key_events per video unless severity is high.
   - NEVER list the same object twice in overlapping times (e.g. two "forklift on sidewalk" lines).
   - SKIP idle parked vehicles, mannequins, generic pedestrians unless tied to action/hazard.
   - Prefer: conflicts, blocking, deliveries, jaywalking, construction hazards, brands/signs, near-misses.
   - label: 3–8 word headline, Title Case, MUST differ from query_text.
   - query_text: one rich search sentence (action + who/what + where + detail).

Keep JSON compact. No markdown. Close all brackets.
Schema:
{{"search_prompts":["..."],"key_events":[{{"query_text":"...","label":"...","original_video":"...","filename":"...","segment_start_sec":0,"segment_end_sec":5}}]}}
"""


def _video_meta(row: dict) -> Tuple[str, str]:
    ov = str(row.get("original_video") or row.get("source") or "").strip()
    fn = str(row.get("filename") or ov.rsplit("/", 1)[-1])
    return ov, fn


def key_events_from_rollups(rollups: List[dict]) -> List[Dict[str, Any]]:
    """Seed key events from stored video_events_json rollup rows."""
    events: List[Dict[str, Any]] = []
    for row in rollups:
        ov, fn = _video_meta(row)
        if not ov:
            continue
        raw_events = row.get("video_events_json") or "[]"
        try:
            timeline = json.loads(raw_events) if isinstance(raw_events, str) else raw_events
        except json.JSONDecodeError:
            timeline = []
        if not isinstance(timeline, list):
            continue
        for item in timeline:
            if not isinstance(item, dict):
                continue
            desc = str(item.get("description") or item.get("event") or "").strip()
            if not desc or len(desc) < 12:
                continue
            start = float(item.get("start_sec") or item.get("segment_start_sec") or 0)
            end = float(item.get("end_sec") or item.get("segment_end_sec") or start + 5)
            label = desc[:60].rsplit(" ", 1)[0] if len(desc) > 60 else desc
            if len(label) < 8:
                label = desc[:40]
            events.append({
                "query_text": desc,
                "label": label.title() if label == desc[: len(label)] else label,
                "original_video": ov,
                "filename": fn,
                "segment_start_sec": start,
                "segment_end_sec": end,
                "source": "rollup",
            })
    return events


def _format_corpus(rollups: List[dict], segments: List[dict], max_segment_lines: int) -> str:
    parts: List[str] = []

    if rollups:
        parts.append("=== VIDEO ROLLUPS (prefer for key_events) ===")
        for row in rollups[:30]:
            ov, fn = _video_meta(row)
            summary_raw = row.get("video_summary_json") or ""
            summary_text = summary_raw
            try:
                parsed = json.loads(summary_raw) if summary_raw else {}
                if isinstance(parsed, dict):
                    summary_text = str(parsed.get("video_summary") or summary_raw)[:600]
            except json.JSONDecodeError:
                summary_text = str(summary_raw)[:600]
            events_raw = str(row.get("video_events_json") or "")[:1200]
            parts.append(
                f"- video={ov} | file={fn}\n"
                f"  summary: {summary_text}\n"
                f"  timeline_events: {events_raw}"
            )

    if segments:
        parts.append("\n=== SAMPLE SEGMENTS (for search_prompts; do not emit one event per line) ===")
        for seg in segments[:max_segment_lines]:
            ov, fn = _video_meta(seg)
            sn = int(seg.get("segment_number") or 0)
            start = float(seg.get("segment_start_sec") or 0)
            end = float(seg.get("segment_end_sec") or start + 5)
            cap = str(seg.get("dense_caption") or seg.get("reasoning_content") or "")[:350]
            objs = str(seg.get("object_classes") or "")
            parts.append(
                f"- video={ov} | file={fn} | seg={sn} | {start:.0f}-{end:.0f}s | objects={objs} | {cap}"
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
    q = ev.query_text.strip()
    lbl = (ev.label or "").strip()
    if not lbl or lbl.lower() == q.lower():
        lbl = ""
    return ev.model_copy(update={"query_text": q, "label": lbl})


def generate_suggestions(
    settings: Settings,
    rollups: List[dict],
    segments: List[dict],
) -> Tuple[List[str], List[Dict[str, Any]], str]:
    """Call Cosmos; merge rollup timeline + LLM output; dedupe."""
    if not rollups and not segments:
        return [], [], ""

    batch_id = _new_batch_id()
    rollup_events = key_events_from_rollups(rollups)
    segment_lines = min(settings.suggestions_max_segments, 48)
    corpus = _format_corpus(rollups, segments, segment_lines)
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
        f"Corpus: {len(rollups)} video rollups, {len(segments)} sample segments, "
        f"{len(rollup_events)} pre-parsed rollup timeline events.\n\n{corpus}"
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
            "rollups": len(rollups),
            "segments_sampled": len(segments),
            "rollup_events_seed": len(rollup_events),
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
    ])[: settings.suggestions_search_count]

    llm_events: List[Dict[str, Any]] = []
    for ev in data.get("key_events", []):
        if not isinstance(ev, dict) or not ev.get("query_text"):
            continue
        normalized = _normalize_key_event(KeyEventSuggestion.model_validate(ev))
        llm_events.append(normalized.model_dump())

    merged = dedupe_key_events(rollup_events + llm_events)
    merged.sort(key=lambda e: (str(e.get("original_video")), float(e.get("segment_start_sec") or 0)))
    events = merged[: settings.suggestions_events_count]

    return prompts, events, batch_id
