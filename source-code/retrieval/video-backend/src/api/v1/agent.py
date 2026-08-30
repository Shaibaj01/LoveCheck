"""
Thin agent endpoint: plan → search → grounded answer using tool APIs.
"""
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.schemas.search import VideoSearchRequest, VideoSearchResponse
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
                "summary": seg.get("reasoning_content") or "",
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
        answer = search_response.results[0].reasoning_content
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


def _answer_from_search(search_response: VideoSearchResponse) -> str:
    if search_response.llm_synthesis:
        synth = search_response.llm_synthesis
        if isinstance(synth, dict):
            return synth.get("response", "")
        return getattr(synth, "response", "") or ""
    if search_response.chunk_results:
        chunk = search_response.chunk_results[0]
        return chunk.reasoning_content or ""
    if search_response.results:
        hit = search_response.results[0]
        return hit.reasoning_content or ""
    return "No matching segments found."


def _chunk_evidence_summary(search_response: VideoSearchResponse) -> list:
    summaries = []
    for chunk in search_response.chunk_results[:10]:
        summaries.append({
            "original_video": chunk.original_video,
            "filename": chunk.filename,
            "similarity_score": chunk.similarity_score,
            "best_match_start_sec": chunk.best_match_start_sec,
            "best_match_end_sec": chunk.best_match_end_sec,
            "matched_segment_count": chunk.matched_segment_count,
            "preview_source": chunk.preview_source,
        })
    return summaries


@router.post("/search-and-answer", response_model=AgentAskResponse)
async def agent_search_and_answer(
    request: VideoSearchRequest,
    current_user: CurrentUser,
):
    """
    Full hybrid search with filters (scope, time, metadata) then grounded answer.

    Same request body as POST /search; returns agent-shaped response with chunk evidence.
    """
    search_response = await search_videos(request, current_user)
    answer = _answer_from_search(search_response)

    llm_synthesis = search_response.llm_synthesis
    if llm_synthesis is not None and hasattr(llm_synthesis, "model_dump"):
        llm_synthesis = llm_synthesis.model_dump()

    return AgentAskResponse(
        answer=answer,
        tool_used="search_hybrid",
        evidence={
            "query": search_response.query,
            "segment_hit_count": search_response.total,
            "chunk_count": search_response.chunk_total,
            "permission_filtered": search_response.permission_filtered,
            "embedding_time_ms": search_response.embedding_time_ms,
            "search_time_ms": search_response.search_time_ms,
            "chunks": _chunk_evidence_summary(search_response),
            "top_segment_sources": [r.source for r in search_response.results[:5]],
            "llm_synthesis": llm_synthesis,
        },
    )
