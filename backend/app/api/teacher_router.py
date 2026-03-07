from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from . import db

router = APIRouter(prefix="/api/teacher", tags=["teacher"])


class AddressedRequest(BaseModel):
    tag_ids: list[int]


@router.get("/{session_id}/dashboard")
async def teacher_dashboard(session_id: str):
    """Returns confusion tags grouped by category + current lecture context."""

    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    context = db.get_context(session_id) or {
        "current_subtopic": session.get("topic", "unknown"),
        "key_terms": [],
        "examples": [],
    }

    tag_groups = db.get_escalations_grouped(session_id)

    return {
        "session_id": session_id,
        "topic": session.get("topic", ""),
        "is_active": bool(session.get("is_active", False)),
        "context": {
            "current_subtopic": context.get("current_subtopic", "unknown"),
            "key_terms": context.get("key_terms", []),
            "examples": context.get("examples", []),
        },
        "tag_groups": tag_groups,
    }


@router.post("/{session_id}/addressed")
async def mark_addressed(session_id: str, body: AddressedRequest):
    """Professor marks confusion tags as addressed."""

    if not body.tag_ids:
        raise HTTPException(status_code=400, detail="No tag IDs provided")

    db.mark_escalations_addressed(body.tag_ids)
    return {"ok": True, "addressed": body.tag_ids}


@router.get("/{session_id}/context")
async def get_context(session_id: str):
    """Returns the current extracted lecture context."""

    context = db.get_context(session_id)
    if not context:
        return {"current_subtopic": "unknown", "key_terms": [], "examples": []}

    return {
        "current_subtopic": context["current_subtopic"],
        "key_terms": context["key_terms"],
        "examples": context["examples"],
        "updated_at": context.get("updated_at", ""),
    }
