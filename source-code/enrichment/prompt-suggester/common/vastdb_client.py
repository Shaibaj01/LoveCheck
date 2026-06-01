"""VastDB reads (segment captions) and writes (prompts/events table)."""
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

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

SEGMENT_COLUMNS = (
    "source", "filename", "original_video", "dense_caption", "reasoning_content",
    "segment_number", "segment_start_sec", "segment_end_sec", "upload_timestamp",
    "object_classes", "row_kind",
)


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

    def fetch_recent_segments(self) -> List[dict]:
        """Segment rows in lookback window with captions (no vector columns)."""
        rows: List[dict] = []
        cutoff = datetime.now(timezone.utc) - timedelta(
            hours=self.settings.suggestions_lookback_hours
        )
        with self.session.transaction() as tx:
            bucket = tx.bucket(self.bucket)
            db_schema = bucket.schema(self.schema_name)
            table = db_schema.table(self.table_name)
            full = table.columns()
            cols = [f.name for f in full if f.name in SEGMENT_COLUMNS]
            if not cols:
                return []
            result = table.select(columns=cols, internal_row_id=False)
            arrow = result.read_all()

        if arrow.num_rows == 0:
            return []

        for row in arrow.to_pylist():
            kind = str(row.get("row_kind") or "").strip().lower()
            if kind and kind not in ("", "segment"):
                continue
            cap = str(row.get("dense_caption") or row.get("reasoning_content") or "").strip()
            if not cap:
                continue
            ts = row.get("upload_timestamp")
            if ts is not None and hasattr(ts, "to_pydatetime"):
                ts_dt = ts.to_pydatetime()
                if ts_dt.tzinfo is None:
                    ts_dt = ts_dt.replace(tzinfo=timezone.utc)
                if ts_dt < cutoff:
                    continue
            rows.append(row)
        return rows

    def list_distinct_videos(self, segments: List[dict]) -> List[str]:
        videos = {
            str(s.get("original_video") or s.get("source") or "").strip()
            for s in segments
        }
        return sorted(v for v in videos if v)

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
            label = str(ev.get("label") or ev.get("description") or q)[:200]
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
