"""Short-lived in-process caches for expensive VastDB / S3 reads."""
from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar

T = TypeVar("T")

# Shared across requests in one backend worker process.
ROW_CACHE_TTL_SEC = 45.0
S3_COUNT_CACHE_TTL_SEC = 300.0
DISTINCT_VALUES_CACHE_TTL_SEC = 120.0
PROMPTS_CACHE_TTL_SEC = 60.0


class _TTLCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: Dict[str, Tuple[float, Any]] = {}

    def get_or_set(self, key: str, ttl_sec: float, factory: Callable[[], T]) -> T:
        now = time.monotonic()
        with self._lock:
            hit = self._entries.get(key)
            if hit is not None and now < hit[0]:
                return hit[1]  # type: ignore[return-value]

        value = factory()
        with self._lock:
            self._entries[key] = (now + ttl_sec, value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


_row_cache = _TTLCache()
_s3_cache = _TTLCache()
_distinct_cache = _TTLCache()
_prompts_cache = _TTLCache()


def cached_table_rows(cache_key: str, ttl_sec: float, loader: Callable[[], List[dict]]) -> List[dict]:
    rows = _row_cache.get_or_set(cache_key, ttl_sec, loader)
    return list(rows)


def cached_s3_mp4_count(bucket: str, ttl_sec: float, loader: Callable[[], int]) -> int:
    return _s3_cache.get_or_set(f"s3-mp4:{bucket}", ttl_sec, loader)


def cached_distinct_values(
    cache_key: str,
    ttl_sec: float,
    loader: Callable[[], Dict[str, List[str]]],
) -> Dict[str, List[str]]:
    return _distinct_cache.get_or_set(cache_key, ttl_sec, loader)


def cached_prompt_rows(cache_key: str, ttl_sec: float, loader: Callable[[], List[dict]]) -> List[dict]:
    rows = _prompts_cache.get_or_set(cache_key, ttl_sec, loader)
    return list(rows)


def clear_read_caches() -> None:
    """Drop cached table and prompt scans after a delete."""
    _row_cache.clear()
    _s3_cache.clear()
    _distinct_cache.clear()
    _prompts_cache.clear()
