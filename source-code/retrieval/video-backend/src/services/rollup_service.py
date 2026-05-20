"""
Video-level rollup: merge segment structured JSON into one timeline summary row.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional

from src.models.user import User
from src.services.llm_service import get_llm_service
from src.services.vastdb_service import get_vastdb_service

logger = logging.getLogger(__name__)

ROLLUP_SYSTEM_PROMPT = """You are a video analyst merging segment-level structured evidence into one parent-video summary.
Rules:
- Use only the provided segment JSON facts.
- Produce valid JSON only (no markdown fences).
- Schema:
{
  "video_summary": "2-4 sentence factual overview of the full video",
  "events": [
    {"start_sec": 0.0, "end_sec": 5.0, "description": "what happened", "objects": ["person"]}
  ]
}
- events must be ordered by start_sec and must not invent timestamps outside provided segment ranges."""


class RollupService:
    def build_rollup(self, original_video: str, user: User, force: bool = False) -> Dict[str, Any]:
        vastdb = get_vastdb_service()
        existing = vastdb.get_video_summary_row(original_video, user)
        if existing and not force:
            return {
                "status": "exists",
                "original_video": original_video,
                "video_summary_json": existing.get("video_summary_json"),
                "video_events_json": existing.get("video_events_json"),
                "segment_count": existing.get("segment_count", 0),
            }

        segments = vastdb.list_segments_for_video(original_video, user)
        if not segments:
            raise ValueError(f"No accessible segments found for video: {original_video}")

        evidence: List[Dict[str, Any]] = []
        for seg in segments:
            structured: Dict[str, Any] = {}
            raw = seg.get("vlm_structured") or ""
            if raw:
                try:
                    structured = json.loads(raw)
                except json.JSONDecodeError:
                    structured = {"raw": raw}
            evidence.append({
                "segment_number": seg.get("segment_number"),
                "segment_start_sec": seg.get("segment_start_sec"),
                "segment_end_sec": seg.get("segment_end_sec"),
                "dense_caption": seg.get("dense_caption"),
                "object_classes": seg.get("object_classes"),
                "structured": structured,
            })

        llm = get_llm_service()
        user_message = (
            f"Parent video: {original_video}\n"
            f"Segment evidence ({len(evidence)} segments):\n"
            f"{json.dumps(evidence, ensure_ascii=False)[:120000]}"
        )
        response = llm._call_llm_api(user_message, system_prompt=ROLLUP_SYSTEM_PROMPT)
        raw_text = (response.get("content") or "").strip()
        parsed = self._parse_rollup_json(raw_text)

        summary_json = json.dumps(
            {"video_summary": parsed.get("video_summary", ""), "segment_count": len(evidence)},
            ensure_ascii=False,
        )
        events_json = json.dumps(parsed.get("events", []), ensure_ascii=False)

        stored = vastdb.store_video_summary_row(
            original_video=original_video,
            user=user,
            video_summary_json=summary_json,
            video_events_json=events_json,
            reference_segment=segments[0],
        )
        if not stored:
            raise RuntimeError("Failed to store video summary row in VastDB")

        return {
            "status": "created",
            "original_video": original_video,
            "video_summary_json": summary_json,
            "video_events_json": events_json,
            "segment_count": len(evidence),
        }

    @staticmethod
    def _parse_rollup_json(raw: str) -> Dict[str, Any]:
        text = raw.strip()
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            text = match.group(0)
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
        return {"video_summary": raw[:2000], "events": []}


_rollup_service: Optional[RollupService] = None


def get_rollup_service() -> RollupService:
    global _rollup_service
    if _rollup_service is None:
        _rollup_service = RollupService()
    return _rollup_service
