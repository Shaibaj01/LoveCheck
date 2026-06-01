"""VastDB reads (summaries + sampled segments) and writes (prompts/events table)."""
import hashlib
import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

import pyarrow as pa
import vastdb

from . import vastdb_patch  # noqa: F401 — apply SDK patch on import
from .models import Settings

logger = logging.getLogger(__name__)

PROMPTS_SCHEMA = pa.schema([
    ("pk", pa.utf8()),
    ("kind", pa.utf8()),
    ("query_text", pa.utf8()),
    ("label", pa.utf8()),
    ("original_video", pa.utf8()),
    ("filename", pa.utf8()),
    ("segment_start_sec", pa.float64()),
    ("segment_end_sec", pa.float64()),
    ("generated_at", pa.timestamp("ns")),
    ("batch_id", pa.utf8()),
    ("is_active", pa.bool_()),
])

READ_COLUMNS = (
    "source", "filename", "original_video", "dense_caption", "reasoning_content",
    "segment_number", "segment_start_sec", "segment_end_sec", "upload_timestamp",
    "object_classes", "row_kind", "video_summary_json", "video_events_json",
)

MAX_SAMPLE_SEGMENTS_PER_VIDEO = 4


class VastDBClient:
    """VastDB client for prompt-suggester enrichment."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.table_name = settings.vdbcollection
        self.prompts_table_name = settings.vdbpromptscollection
        self.bucket = settings.vdbbucket
        self.schema_name = settings.vdbschema

        endpoint = settings.vdbendpoint
        if not endpoint.startswith(("http://", "https://")):
            endpoint = f"http://{endpoint}"
        self.session = vastdb.connect(
            endpoint=endpoint,
            access=settings.vdbaccesskey,
            secret=settings.vdbsecretkey,
            ssl_verify=False,
        )

    def _in_lookback(self, row: dict, cutoff: datetime) -> bool:
        ts = row.get("upload_timestamp")
        if ts is None or not hasattr(ts, "to_pydatetime"):
            return True
        ts_dt = ts.to_pydatetime()
        if ts_dt.tzinfo is None:
            ts_dt = ts_dt.replace(tzinfo=timezone.utc)
        return ts_dt >= cutoff

    def _sample_segments(self, segments: List[dict]) -> List[dict]:
        by_video: Dict[str, List[dict]] = defaultdict(list)
        for seg in segments:
            ov = str(seg.get("original_video") or seg.get("source") or "").strip()
            if ov:
                by_video[ov].append(seg)

        sampled: List[dict] = []
        for segs in by_video.values():
            segs.sort(key=lambda s: int(s.get("segment_number") or 0))
            n = len(segs)
            if n <= MAX_SAMPLE_SEGMENTS_PER_VIDEO:
                sampled.extend(segs)
                continue
            step = n / MAX_SAMPLE_SEGMENTS_PER_VIDEO
            for i in range(MAX_SAMPLE_SEGMENTS_PER_VIDEO):
                sampled.append(segs[min(int(i * step), n - 1)])
        return sampled

    def fetch_corpus(self) -> Tuple[List[dict], List[dict]]:
        """
        Returns (video_rollups, sampled_segments) within lookback window.
        Rollups are row_kind=video_summary; segments are capped per video.
        """
        rollups: List[dict] = []
        segments: List[dict] = []
        cutoff = datetime.now(timezone.utc) - timedelta(
            hours=self.settings.suggestions_lookback_hours
        )

        with self.session.transaction() as tx:
            bucket = tx.bucket(self.bucket)
            db_schema = bucket.schema(self.schema_name)
            table = db_schema.table(self.table_name)
            full = table.columns()
            cols = [f.name for f in full if f.name in READ_COLUMNS]
            if not cols:
                return [], []
            result = table.select(columns=cols, internal_row_id=False)
            arrow = result.read_all()

        if arrow.num_rows == 0:
            return [], []

        for row in arrow.to_pylist():
            if not self._in_lookback(row, cutoff):
                continue
            kind = str(row.get("row_kind") or "").strip().lower()
            if kind == "video_summary":
                rollups.append(row)
                continue
            if kind and kind not in ("", "segment"):
                continue
            cap = str(row.get("dense_caption") or row.get("reasoning_content") or "").strip()
            if cap:
                segments.append(row)

        return rollups, self._sample_segments(segments)

    def fetch_recent_segments(self) -> List[dict]:
        """Backward-compatible: sampled segments only."""
        _, segments = self.fetch_corpus()
        return segments

    def list_distinct_videos(self, segments: List[dict], rollups: List[dict]) -> List[str]:
        videos = set()
        for row in segments + rollups:
            ov = str(row.get("original_video") or row.get("source") or "").strip()
            if ov:
                videos.add(ov)
        return sorted(videos)

    def ensure_prompts_table(self) -> None:
        with self.session.transaction() as tx:
            bucket = tx.bucket(self.bucket)
            db_schema = bucket.schema(self.schema_name, fail_if_missing=False)
            if db_schema is None:
                db_schema = bucket.create_schema(self.schema_name, fail_if_exists=False)
            table = db_schema.table(self.prompts_table_name, fail_if_missing=False)
            if table is None:
                db_schema.create_table(self.prompts_table_name, columns=PROMPTS_SCHEMA)

    def store_suggestions(
        self,
        batch_id: str,
        search_prompts: List[str],
        key_events: List[Dict[str, Any]],
    ) -> int:
        """Insert one batch of search prompts and key events."""
        now = datetime.now(timezone.utc)
        records: List[dict] = []

        for text in search_prompts[: self.settings.suggestions_search_count]:
            q = text.strip()
            if not q:
                continue
            records.append({
                "pk": hashlib.md5(f"search:{q}".encode()).hexdigest(),
                "kind": "search_prompt",
                "query_text": q,
                "label": q[:120],
                "original_video": "",
                "filename": "",
                "segment_start_sec": 0.0,
                "segment_end_sec": 0.0,
                "generated_at": now,
                "batch_id": batch_id,
                "is_active": True,
            })

        for ev in key_events[: self.settings.suggestions_events_count]:
            q = str(ev.get("query_text") or ev.get("query") or "").strip()
            if not q:
                continue
            ov = str(ev.get("original_video") or "").strip()
            start = float(ev.get("segment_start_sec") or 0)
            end = float(ev.get("segment_end_sec") or start + 5)
            label = str(ev.get("label") or "").strip()[:200]
            if label.lower() == q.lower():
                label = ""
            pk_src = f"event:{ov}:{start}:{q}"
            records.append({
                "pk": hashlib.md5(pk_src.encode()).hexdigest(),
                "kind": "key_event",
                "query_text": q,
                "label": label,
                "original_video": ov,
                "filename": str(ev.get("filename") or "").strip(),
                "segment_start_sec": start,
                "segment_end_sec": end,
                "generated_at": now,
                "batch_id": batch_id,
                "is_active": True,
            })

        if not records:
            return 0

        self.ensure_prompts_table()
        arrow = pa.Table.from_pylist(records, schema=PROMPTS_SCHEMA)

        with self.session.transaction() as tx:
            bucket = tx.bucket(self.bucket)
            db_schema = bucket.schema(self.schema_name)
            table = db_schema.table(self.prompts_table_name)
            table.insert(arrow)

        return len(records)
