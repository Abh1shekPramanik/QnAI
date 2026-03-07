from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from . import db
from .recall_router import manager
from ..services import context_service

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

class EscalationCreate(BaseModel):
    student_id: str
    tag: str
    query: str = ""

@router.post("/{session_id}/escalation")
async def add_escalation(session_id: str, body: EscalationCreate):
    entry = db.add_escalation(session_id, body.student_id, body.tag, body.query)
    await manager.broadcast({
        "type": "escalation_added",
        "data": entry
    })
    return {"ok": True, "escalation": entry}

@router.get("/{session_id}/escalations")
async def get_escalations(session_id: str):
    return db.get_escalations(session_id)

@router.get("/{session_id}/members")
async def get_members(session_id: str):
    return db.get_session_members(session_id)


# ── Test / Dev helpers ──

@router.post("/{session_id}/start-extraction")
async def start_extraction(session_id: str):
    """Manually start the 60s context extraction loop (for testing without Recall)."""
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    context_service.start_extraction(session_id)
    return {"ok": True, "message": f"Extraction loop started for {session_id}"}


class SeedTranscriptRequest(BaseModel):
    speaker: str = "Professor"
    text: str

@router.post("/{session_id}/seed-transcript")
async def seed_transcript(session_id: str, body: SeedTranscriptRequest):
    """Manually add a transcript chunk (for testing without Recall/Zoom)."""
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    db.save_transcript(session_id, body.speaker, body.text, is_final=True)
    return {"ok": True, "message": f"Transcript chunk saved for {session_id}"}