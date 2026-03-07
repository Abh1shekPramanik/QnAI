import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from . import db
from .recall_router import manager
from ..utils.gemini import get_ai_brief, compress_query, categorize_tag

router = APIRouter(prefix="/api/student", tags=["student"])


class LostRequest(BaseModel):
    query: str
    student_id: str = "anonymous"


class EscalateRequest(BaseModel):
    query_id: str


# ── Layer 1: Student is confused → get AI brief ──

@router.post("/{session_id}/lost")
async def student_lost(session_id: str, body: LostRequest):
    """Student submits a confusion query. Returns a short AI explanation."""

    # Validate session exists
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get current context (from the 60s extraction loop)
    context = db.get_context(session_id) or {
        "current_subtopic": session.get("topic", "unknown"),
        "key_terms": [],
        "examples": [],
    }

    # Get recent transcript for extra grounding
    transcripts = db.get_transcripts(session_id)
    recent_text = "\n".join([f"{t['speaker']}: {t['text']}" for t in transcripts[-15:]])

    # Call Gemini → AI brief (2-3 sentences)
    try:
        answer = get_ai_brief(body.query, context, recent_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")

    # Save as pending query so student can escalate later
    query_id = str(uuid.uuid4())
    db.save_pending_query(query_id, session_id, body.student_id, body.query, answer)

    return {
        "answer": answer,
        "query_id": query_id,
    }


# ── Layer 2: Still confused → compress + categorize → send to professor ──

@router.post("/{session_id}/escalate")
async def student_escalate(session_id: str, body: EscalateRequest):
    """Student is still confused after AI brief. Sends anonymous tag to professor."""

    # Look up the pending query
    pending = db.get_pending_query(body.query_id)
    if not pending:
        raise HTTPException(status_code=404, detail="Query not found. Submit /lost first.")

    if pending["session_id"] != session_id:
        raise HTTPException(status_code=400, detail="Query does not belong to this session.")

    original_query = pending["query"]

    # Gemini Call 3: compress to 3-4 word tag
    try:
        tag = compress_query(original_query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tag compression failed: {str(e)}")

    # Gemini Call 4: categorize the tag
    try:
        existing_cats = db.get_existing_categories(session_id)
        category = categorize_tag(tag, existing_cats)
    except Exception as e:
        # If categorization fails, use a fallback
        category = "Uncategorized"

    # Save escalation with category
    entry = db.add_escalation_with_category(
        session_id, pending["student_id"], tag, category, original_query
    )

    # Broadcast to professor dashboard via WebSocket
    await manager.broadcast({
        "type": "tag_new",
        "data": entry,
    })

    return {
        "tag": tag,
        "category": category,
        "message": "Your confusion has been anonymously sent to the professor.",
    }
