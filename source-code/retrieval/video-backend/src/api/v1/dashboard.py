"""Live VastDB data dashboard API."""
import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status

from src.services.auth_service import CurrentUser
from src.services.vastdb_service import get_vastdb_service
from src.schemas.dashboard import DashboardStatsResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    current_user: CurrentUser,
    scope: str = Query(default="all", pattern="^(all|mine|public)$"),
):
    """
    Aggregate statistics for rows in the VastDB collection visible to the current user.

    Includes overview counts, detected objects, upload metadata, upload timeline,
    ingest quality signals, and recent videos.
    """
    try:
        vastdb = get_vastdb_service()
        stats = vastdb.get_dashboard_stats(current_user, scope=scope)
        return DashboardStatsResponse(**stats)
    except Exception as exc:
        logger.error("[DASHBOARD] Unexpected failure building stats: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load dashboard stats: {exc}",
        ) from exc
