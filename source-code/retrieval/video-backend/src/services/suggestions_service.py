"""Read LLM-generated search prompts and key events from VastDB."""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pyarrow as pa
import vastdb
import vastdb._internal as _internal

from src.config import get_settings

logger = logging.getLogger(__name__)

_original_build = _internal.build_query_data_request


def _apply_vector_patch():
    def patched(schema, predicate, field_names):
        supported, skip = [], set()
        for field in schema:
            t = str(field.type)
            if "fixed_size_list" in t or ("list<" in t and "float" in t):
                skip.add(field.name)
            else:
                supported.append(field)
        names = [n for n in field_names if n not in skip]
        return _original_build(pa.schema(supported), predicate, names)

    _internal.build_query_data_request = patched


_apply_vector_patch()

PROMPT_COLUMNS = (
    "pk", "kind", "query_text", "label", "original_video", "filename",
    "segment_start_sec", "segment_end_sec", "generated_at", "batch_id", "is_active",
)


class SuggestionsService:
    def __init__(self):
        self.settings = get_settings()
        endpoint = self.settings.vdb_endpoint
        if not endpoint.startswith(("http://", "https://")):
            endpoint = f"http://{endpoint}"
        self._session = vastdb.connect(
            endpoint=endpoint,
            access=self.settings.vdb_access_key,
            secret=self.settings.vdb_secret_key,
            ssl_verify=False,
        )
        self._table_name = getattr(
            self.settings, "vdb_prompts_collection", "vss2-prompts-events"
        )

    def _read_all_rows(self) -> List[dict]:
        with self._session.transaction() as tx:
            bucket = tx.bucket(self.settings.vdb_bucket)
            db_schema = bucket.schema(self.settings.vdb_schema)
            try:
                table = db_schema.table(self._table_name)
            except Exception:
                return []
            result = table.select(columns=list(PROMPT_COLUMNS), internal_row_id=False)
            arrow = result.read_all()
        if arrow.num_rows == 0:
            return []
        import pandas as pd

        return [row.to_dict() for _, row in arrow.to_pandas().iterrows()]

    def _latest_batch_id(self, rows: List[dict]) -> Optional[str]:
        if not rows:
            return None
        best_ts = None
        best_batch = None
        for row in rows:
            if not row.get("is_active"):
                continue
            ts = row.get("generated_at")
            bid = str(row.get("batch_id") or "")
            if not bid:
                continue
            if ts is not None and (best_ts is None or str(ts) > str(best_ts)):
                best_ts = ts
                best_batch = bid
        return best_batch

    def get_suggestions(self) -> Dict[str, Any]:
        rows = self._read_all_rows()
        batch_id = self._latest_batch_id(rows)
        if not batch_id:
            return {
                "batch_id": None,
                "generated_at": None,
                "search_prompts": [],
                "key_events": [],
                "table": f"{self.settings.vdb_bucket}/{self.settings.vdb_schema}/{self._table_name}",
            }

        active = [r for r in rows if str(r.get("batch_id")) == batch_id and r.get("is_active")]

        prompts: List[str] = []
        events: List[Dict[str, Any]] = []
        gen_at = None

        for row in active:
            kind = str(row.get("kind") or "")
            if kind == "search_prompt":
                q = str(row.get("query_text") or "").strip()
                if q and q not in prompts:
                    prompts.append(q)
            elif kind == "key_event":
                events.append({
                    "query_text": str(row.get("query_text") or ""),
                    "label": str(row.get("label") or row.get("query_text") or ""),
                    "original_video": str(row.get("original_video") or ""),
                    "filename": str(row.get("filename") or ""),
                    "segment_start_sec": float(row.get("segment_start_sec") or 0),
                    "segment_end_sec": float(row.get("segment_end_sec") or 0),
                })
            ts = row.get("generated_at")
            if ts is not None:
                gen_at = ts

        events.sort(key=lambda e: (e["segment_start_sec"], e["filename"]))

        generated_iso = None
        if gen_at is not None and hasattr(gen_at, "isoformat"):
            generated_iso = gen_at.isoformat()
        elif gen_at is not None:
            generated_iso = str(gen_at)

        return {
            "batch_id": batch_id,
            "generated_at": generated_iso,
            "search_prompts": prompts[:10],
            "key_events": events,
            "table": f"{self.settings.vdb_bucket}/{self.settings.vdb_schema}/{self._table_name}",
        }


_service: Optional[SuggestionsService] = None


def get_suggestions_service() -> SuggestionsService:
    global _service
    if _service is None:
        _service = SuggestionsService()
    return _service
