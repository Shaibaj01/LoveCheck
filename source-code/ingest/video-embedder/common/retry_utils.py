"""Transient-error handling for ingest model calls.

Policy: retry a connection error once in-process; if it still fails (or the
server returns a transient 5xx/429), raise ``TransientError`` so the VastPipeline
(Kafka) redelivers the event. The writer's dedup makes redelivery safe.
Permanent/bad-input failures are not raised here — callers return skipped.
"""
import logging

import requests

_CONN_EXC = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
)
_TRANSIENT_STATUS = (429, 500, 502, 503, 504)


class TransientError(Exception):
    """Retryable failure — hand the retry off to the VastPipeline."""


def post_with_retry(url, *, session=None, **kwargs):
    """POST with a single retry on connection errors, then raise TransientError.

    A transient HTTP status (429/5xx) is also surfaced as TransientError so the
    caller lets the pipeline redeliver instead of acking a lost event.
    """
    poster = session.post if session is not None else requests.post
    try:
        resp = poster(url, **kwargs)
    except _CONN_EXC as exc:
        logging.warning("[RETRY] connection error to %s; retrying once: %s", url, exc)
        try:
            resp = poster(url, **kwargs)
        except _CONN_EXC as exc2:
            raise TransientError(f"connection failed after 1 retry: {exc2}") from exc2
    if resp.status_code in _TRANSIENT_STATUS:
        raise TransientError(f"transient HTTP {resp.status_code}: {resp.text[:300]}")
    return resp
