"""Check whether a segment source is already indexed in VastDB."""
from __future__ import annotations

import hashlib
import logging
from typing import Any, Protocol

import vastdb

logger = logging.getLogger(__name__)


def pk_for_source(source: str) -> str:
    return hashlib.md5(source.encode()).hexdigest()


class VastDbSettings(Protocol):
    vdbendpoint: str
    vdbbucket: str
    vdbschema: str
    vdbaccesskey: str
    vdbsecretkey: str
    vdbcollection: str


class SegmentIndexChecker:
    """VastDB segment lookup with in-process cache."""

    def __init__(self, settings: VastDbSettings):
        endpoint = settings.vdbendpoint
        if not endpoint.startswith(("http://", "https://")):
            endpoint = f"http://{endpoint}"
        self.bucket = settings.vdbbucket
        self.schema_name = settings.vdbschema
        self.table_name = settings.vdbcollection
        self.session = vastdb.connect(
            endpoint=endpoint,
            access=settings.vdbaccesskey,
            secret=settings.vdbsecretkey,
            ssl_verify=False,
        )
        self._indexed_sources: set[str] | None = None

    def _load_indexed_sources(self) -> set[str]:
        with self.session.transaction() as tx:
            bucket = tx.bucket(self.bucket)
            db_schema = bucket.schema(self.schema_name, fail_if_missing=False)
            if db_schema is None:
                return set()
            table = db_schema.table(self.table_name, fail_if_missing=False)
            if table is None:
                return set()
            result = table.select(columns=["source"], internal_row_id=False)
            arrow = result.read_all()
        if arrow.num_rows == 0:
            return set()
        out: set[str] = set()
        for row in arrow.to_pylist():
            source = str(row.get("source") or "").strip()
            if source:
                out.add(source)
        return out

    def is_indexed(self, source: str) -> bool:
        if not source:
            return False
        try:
            if self._indexed_sources is None:
                self._indexed_sources = self._load_indexed_sources()
            return source in self._indexed_sources
        except Exception as exc:
            logger.warning("VastDB indexed check failed for %s: %s", source, exc)
            return False

    def mark_indexed(self, source: str) -> None:
        if source and self._indexed_sources is not None:
            self._indexed_sources.add(source)

    def close(self) -> None:
        if hasattr(self.session, "close"):
            self.session.close()
