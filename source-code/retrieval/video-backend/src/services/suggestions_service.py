"""Read LLM-generated search prompts and key events from VastDB."""
import logging
import re
from typing import Any, Dict, List, Optional, Set

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

    @staticmethod
    def _ts_sort_key(ts: Any) -> float:
        if ts is None:
            return 0.0
        if hasattr(ts, "timestamp"):
            return float(ts.timestamp())
        return float(str(ts))

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

    @staticmethod
    def _row_to_key_event(row: dict) -> Dict[str, Any]:
        query = str(row.get("query_text") or "").strip()
        label = str(row.get("label") or "").strip()
        if label.lower() == query.lower():
            label = ""
        gen_at = row.get("generated_at")
        if gen_at is not None and hasattr(gen_at, "isoformat"):
            gen_at = gen_at.isoformat()
        elif gen_at is not None:
            gen_at = str(gen_at)
        return {
            "query_text": query,
            "label": label,
            "original_video": str(row.get("original_video") or ""),
            "filename": str(row.get("filename") or ""),
            "segment_start_sec": float(row.get("segment_start_sec") or 0),
            "segment_end_sec": float(row.get("segment_end_sec") or 0),
            "generated_at": gen_at,
            "batch_id": str(row.get("batch_id") or ""),
        }

    @staticmethod
    def _event_tokens(text: str) -> Set[str]:
        stop = {"the", "and", "for", "with", "near", "along", "street", "sidewalk", "road"}
        return {
            w for w in re.findall(r"[a-z0-9]+", (text or "").lower())
            if len(w) > 2 and w not in stop
        }

    def _events_similar(self, a: str, b: str) -> bool:
        ta, tb = self._event_tokens(a), self._event_tokens(b)
        if not ta or not tb:
            return a.strip().lower() == b.strip().lower()
        return len(ta & tb) / len(ta | tb) >= 0.52

    def _key_events_for_batch(self, rows: List[dict], batch_id: str) -> List[Dict[str, Any]]:
        """Latest batch only, timeline order, fuzzy dedupe (avoids stacked duplicate runs)."""
        event_rows = [
            r for r in rows
            if str(r.get("kind") or "") == "key_event"
            and r.get("is_active")
            and str(r.get("batch_id") or "") == batch_id
        ]
        event_rows.sort(
            key=lambda r: (
                float(r.get("segment_start_sec") or 0),
                str(r.get("original_video") or ""),
            )
        )
        kept: List[Dict[str, Any]] = []
        for row in event_rows:
            ev = self._row_to_key_event(row)
            q = ev["query_text"]
            if not q:
                continue
            dup = False
            for existing in kept:
                if str(existing.get("original_video")) != str(ev.get("original_video")):
                    continue
                t0 = float(existing.get("segment_start_sec") or 0)
                t1 = float(ev.get("segment_start_sec") or 0)
                if abs(t0 - t1) > 12:
                    continue
                if self._events_similar(q, existing["query_text"]) or self._events_similar(
                    ev.get("label") or q, existing.get("label") or existing["query_text"]
                ):
                    dup = True
                    break
            if not dup:
                kept.append(ev)
        return kept

    def get_suggestions(self) -> Dict[str, Any]:
        rows = self._read_all_rows()
        batch_id = self._latest_batch_id(rows)
        table = f"{self.settings.vdb_bucket}/{self.settings.vdb_schema}/{self._table_name}"

        if not batch_id and not rows:
            return {
                "batch_id": None,
                "generated_at": None,
                "search_prompts": [],
                "key_events": [],
                "key_events_count": 0,
                "table": table,
            }

        prompts: List[str] = []
        gen_at = None
        if batch_id:
            for row in rows:
                if str(row.get("batch_id")) != batch_id or not row.get("is_active"):
                    continue
                if str(row.get("kind") or "") != "search_prompt":
                    continue
                q = str(row.get("query_text") or "").strip()
                if q and q not in prompts:
                    prompts.append(q)
                ts = row.get("generated_at")
                if ts is not None:
                    gen_at = ts

        events = self._key_events_for_batch(rows, batch_id) if batch_id else []

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
            "key_events_count": len(events),
            "table": table,
        }


_service: Optional[SuggestionsService] = None


def get_suggestions_service() -> SuggestionsService:
    global _service
    if _service is None:
        _service = SuggestionsService()
    return _service
