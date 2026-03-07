"""
Issue #8 — Topic Setter (Backend)
FastAPI router that lets the professor set/update the current lecture topic.
This topic feeds into all Gemini calls (Issues #4, #6) as context.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime, timezone

router = APIRouter(prefix="/api/topic", tags=["topic"])


# ── Models ────────────────────────────────────────────────────────
class TopicUpdate(BaseModel):
    topic: str = Field(..., min_length=1, max_length=300, examples=["Linked Lists & Pointers"])


class TopicResponse(BaseModel):
    topic: str
    updated_at: str
    updated_by: str


# ── In-memory store (swap for Redis / DB in production) ──────────
_current_topic: dict = {
    "topic": "",
    "updated_at": "",
    "updated_by": "teacher",
}


# ── Routes ────────────────────────────────────────────────────────
@router.get("/", response_model=TopicResponse)
async def get_topic():
    """
    GET /api/topic
    Returns the current lecture topic.
    Polled by SessionContext on the frontend (Issue #3).
    """
    if not _current_topic["topic"]:
        raise HTTPException(status_code=404, detail="No topic has been set yet.")
    return _current_topic


@router.put("/", response_model=TopicResponse)
async def set_topic(body: TopicUpdate):
    """
    PUT /api/topic
    Professor sets or updates the lecture topic.
    """
    _current_topic["topic"] = body.topic.strip()
    _current_topic["updated_at"] = datetime.now(timezone.utc).isoformat()
    _current_topic["updated_by"] = "teacher"
    return _current_topic


@router.delete("/", status_code=204)
async def clear_topic():
    """
    DELETE /api/topic
    Clears the current topic (e.g. end of lecture).
    """
    _current_topic["topic"] = ""
    _current_topic["updated_at"] = ""
    return None