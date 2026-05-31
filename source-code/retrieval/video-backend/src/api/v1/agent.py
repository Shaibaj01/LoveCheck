"""
Thin agent endpoint: plan → search → grounded answer using tool APIs.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.schemas.search import VideoSearchRequest
from src.services.auth_service import CurrentUser
from src.services.llm_service import get_llm_service
from src.services.rollup_service import get_rollup_service
from src.services.vastdb_service import get_vastdb_service
from src.api.v1.search import search_videos

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["Agent"])


class AgentAskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    original_video: Optional[str] = Field(
        default=None,
        description="When set, summarize/list segments for this parent video instead of global search",
    )
    top_k: int = Field(default=10, ge=1, le=50)


class AgentAskResponse(BaseModel):
    answer: str
    tool_used: str
    evidence: Dict[str, Any] = Field(default_factory=dict)


@router.post("/ask", response_model=AgentAskResponse)
async def agent_ask(request: AgentAskRequest, current_user: CurrentUser = None):
    """
    Answer a question using VastDB tools:
    - If original_video is provided → rollup/summary + segment list
    - Else → hybrid search + optional LLM synthesis
    """
    if request.original_video:
        rollup = get_rollup_service()
        try:
            summary = rollup.build_rollup(request.original_video, current_user, force=False)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

        vastdb = get_vastdb_service()
        segments = vastdb.list_segments_for_video(request.original_video, current_user)
        llm = get_llm_service()
        synthesis = llm.synthesize_search_results(
            query=request.question,
            top_results=[
                {
                    "summary": summary.get("video_summary_json", ""),
                    "vlm_structured": summary.get("video_summary_json", ""),
                    "dense_caption": summary.get("video_summary_json", ""),
                    "original_video": request.original_video,
                    "segment_number": 0,
                    "segment_start_sec": 0,
                    "segment_end_sec": 0,
                    "similarity_score": 1.0,
                }
            ],
        )
        return AgentAskResponse(
            answer=synthesis.get("response", ""),
            tool_used="video_summary",
            evidence={"summary": summary, "segment_count": len(segments)},
        )

    search_request = VideoSearchRequest(
        query=request.question,
        top_k=request.top_k,
        include_public=True,
    )
    search_response = await search_videos(search_request, current_user)
    answer = ""
    if search_response.llm_synthesis:
        answer = search_response.llm_synthesis.get("response", "")
    elif search_response.results:
        answer = search_response.results[0].dense_caption or search_response.results[0].reasoning_content
    else:
        answer = "No matching segments found."

    return AgentAskResponse(
        answer=answer,
        tool_used="search_hybrid",
        evidence={
            "result_count": search_response.total,
            "top_sources": [r.source for r in search_response.results[:5]],
        },
    )
