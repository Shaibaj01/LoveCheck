"""Fast per-source VastDB idempotency checks (predicate pushdown, not full table scan)."""
from __future__ import annotations

import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class VastDbSettings(Protocol):
    vdbendpoint: str
    vdbbucket: str
    vdbschema: str
    vdbaccesskey: str
    vdbsecretkey: str
    vdbcollection: str


class SegmentIndexChecker:
    """O(1) indexed lookup via source predicate + in-process cache."""

    def __init__(self, settings: VastDbSettings):
        self.session = None
        self._indexed_sources: set[str] = set()
        endpoint = settings.vdbendpoint
        if not endpoint.startswith(("http://", "https://")):
            endpoint = f"http://{endpoint}"
        self.bucket = settings.vdbbucket
        self.schema_name = settings.vdbschema
        self.table_name = settings.vdbcollection
        try:
            from common import vastdb_patch  # noqa: F401
            import vastdb  # type: ignore
        except (ModuleNotFoundError, ImportError):
            logger.info("vastdb package unavailable; idempotency check disabled")
            return
        self.session = vastdb.connect(
            endpoint=endpoint,
            access=settings.vdbaccesskey,
            secret=settings.vdbsecretkey,
            ssl_verify=False,
        )

    def _source_exists(self, source: str) -> bool:
        if self.session is None:
            return False
        with self.session.transaction() as tx:
            bucket = tx.bucket(self.bucket)
            db_schema = bucket.schema(self.schema_name, fail_if_missing=False)
            if db_schema is None:
                return False
            table = db_schema.table(self.table_name, fail_if_missing=False)
            if table is None:
                return False
            existing = table.select(
                predicate=(table["source"] == source),
                columns=["source"],
                internal_row_id=False,
            ).read_all()
        return existing.num_rows > 0

    def is_indexed(self, source: str) -> bool:
        if not source or self.session is None:
            return False
        if source in self._indexed_sources:
            return True
        try:
            if self._source_exists(source):
                self._indexed_sources.add(source)
                return True
            return False
        except Exception as exc:
            logger.warning("VastDB indexed check failed for %s: %s", source, exc)
            return False

    def mark_indexed(self, source: str) -> None:
        if source:
            self._indexed_sources.add(source)

    def close(self) -> None:
        if self.session is not None and hasattr(self.session, "close"):
            self.session.close()
