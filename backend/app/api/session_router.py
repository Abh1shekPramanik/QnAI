from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List
from . import db
from .recall_router import manager # Reuse the same WebSocket manager

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

class EscalationCreate(BaseModel):
    student_id: str
    tag: str
    query: str = ""

@router.get("/{session_id}/members")
async def get_members(session_id: str):
    members = db.get_session_members(session_id)
    return members

@router.post("/{session_id}/escalation")
async def add_escalation(session_id: str, body: EscalationCreate):
    entry = db.add_escalation(session_id, body.student_id, body.tag, body.query)
    
    # Broadcast to Professor/Students via existing WebSocket
    await manager.broadcast({
        "type": "escalation_added",
        "data": entry
    })
    
    return {"ok": True, "escalation": entry}

@router.get("/{session_id}/escalations")
async def get_escalations(session_id: str):
    return db.get_escalations(session_id)

@router.get("/")
async def list_sessions(professor_id: str = None):
    return db.list_sessions(professor_id)
