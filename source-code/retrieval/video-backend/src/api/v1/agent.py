"""
Thin agent endpoint: plan → search → grounded answer using tool APIs.
"""
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.schemas.search import VideoSearchRequest
from src.services.auth_service import CurrentUser
from src.services.llm_service import get_llm_service
from src.services.vastdb_service import get_vastdb_service
from src.api.v1.search import search_videos

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["Agent"])


class AgentAskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    original_video: Optional[str] = Field(
        default=None,
        description="When set, answer from this parent video's segments instead of global search",
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
    - If original_video is provided → segment evidence + LLM synthesis
    - Else → hybrid search + optional LLM synthesis
    """
    if request.original_video:
        vastdb = get_vastdb_service()
        segments = vastdb.list_segments_for_video(request.original_video, current_user)
        if not segments:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No accessible segments found for video: {request.original_video}",
            )

        top_results = []
        for seg in segments[: request.top_k]:
            top_results.append({
                "summary": seg.get("dense_caption") or seg.get("reasoning_content") or "",
                "vlm_structured": seg.get("vlm_structured") or "",
                "dense_caption": seg.get("dense_caption") or "",
                "reasoning_content": seg.get("reasoning_content") or "",
                "original_video": request.original_video,
                "segment_number": seg.get("segment_number"),
                "segment_start_sec": seg.get("segment_start_sec"),
                "segment_end_sec": seg.get("segment_end_sec"),
                "similarity_score": 1.0,
            })

        llm = get_llm_service()
        synthesis = llm.synthesize_search_results(
            query=request.question,
            top_results=top_results,
        )
        return AgentAskResponse(
            answer=synthesis.get("response", ""),
            tool_used="video_segments",
            evidence={"segment_count": len(segments), "segments_used": len(top_results)},
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
