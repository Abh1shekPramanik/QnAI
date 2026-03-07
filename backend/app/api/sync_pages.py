"""
QnAI — Shared Session State Backend (Issue #3)
FastAPI + WebSocket server that keeps teacher-set topic and transcript
synchronised across all connected teacher / student clients in real time.

Backed by SQLite (db.py) for multiple professors, students, and sessions.

Real-time sync uses native WebSocket rooms (implemented as dicts of
connection sets keyed by session_id). Clients connect to /ws/{session_id}
and receive JSON messages for state updates.

Run with:
    uvicorn sync_pages:app --port 5001 --reload
"""

from __future__ import annotations

import os
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import db

# ──────────────────────────────────────────────
# App
# ──────────────────────────────────────────────
app = FastAPI(title="QnAI Session Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _session_snapshot(session_id: str) -> dict | None:
    s = db.get_session(session_id)
    if not s:
        return None
    members = db.get_session_members(session_id)
    escalations = db.get_escalations(session_id)
    return {
        "session_id": s["id"],
        "title": s["title"],
        "topic": s["topic"],
        "transcript": s["transcript"],
        "professor_id": s["professor_id"],
        "is_active": s["is_active"],
        "members": members,
        "escalations": escalations,
        "updated_at": s["updated_at"],
    }


# ──────────────────────────────────────────────
# WebSocket room manager
# ──────────────────────────────────────────────
class RoomManager:
    """Manages WebSocket connections grouped by session_id (room)."""

    def __init__(self):
        # session_id → set of WebSocket connections
        self.rooms: dict[str, set[WebSocket]] = {}
        # All connections (for global broadcasts)
        self.all_connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket, session_id: str):
        await ws.accept()
        self.all_connections.add(ws)
        if session_id not in self.rooms:
            self.rooms[session_id] = set()
        self.rooms[session_id].add(ws)

    def disconnect(self, ws: WebSocket, session_id: str):
        self.all_connections.discard(ws)
        if session_id in self.rooms:
            self.rooms[session_id].discard(ws)
            if not self.rooms[session_id]:
                del self.rooms[session_id]

    async def send_to_room(self, session_id: str, message: dict):
        """Send a JSON message to all connections in a room."""
        data = json.dumps(message)
        dead = []
        for ws in self.rooms.get(session_id, set()):
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.rooms.get(session_id, set()).discard(ws)
            self.all_connections.discard(ws)

    async def broadcast(self, message: dict):
        """Send a JSON message to ALL connected clients."""
        data = json.dumps(message)
        dead = []
        for ws in self.all_connections:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.all_connections.discard(ws)


manager = RoomManager()


# Helper: broadcast to room + globally (for backward compat)
async def _emit_to_session(session_id: str, event: str, payload: dict):
    message = {"event": event, **payload}
    await manager.send_to_room(session_id, message)
    await manager.broadcast(message)


# ──────────────────────────────────────────────
# Pydantic models
# ──────────────────────────────────────────────
class TopicBody(BaseModel):
    topic: str = ""

class TranscriptBody(BaseModel):
    transcript: str = ""

class EscalationBody(BaseModel):
    tag: str = ""
    student_id: str = "anonymous"
    query: str = ""

class RecallTranscriptBody(BaseModel):
    session_id: str = "session-001"
    speaker: str = "Unknown"
    text: str = ""
    is_final: bool = False


# ──────────────────────────────────────────────
# REST endpoints
# ──────────────────────────────────────────────

@app.get("/api/users")
def api_list_users(role: Optional[str] = None):
    return db.list_users(role)


@app.get("/api/users/{user_id}")
def api_get_user(user_id: str):
    user = db.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.get("/api/sessions")
def api_list_sessions(professor_id: Optional[str] = None):
    return db.list_sessions(professor_id)


@app.get("/api/sessions/{session_id}")
def api_get_session(session_id: str):
    snap = _session_snapshot(session_id)
    if not snap:
        raise HTTPException(status_code=404, detail="Session not found")
    return snap


@app.get("/api/sessions/{session_id}/members")
def api_session_members(session_id: str):
    return db.get_session_members(session_id)


@app.get("/api/students/{student_id}/sessions")
def api_student_sessions(student_id: str):
    return db.get_student_sessions(student_id)


@app.post("/api/sessions/{session_id}/topic")
async def api_set_topic(session_id: str, body: TopicBody):
    db.update_session_topic(session_id, body.topic)
    await _emit_to_session(session_id, "topic_updated", {"topic": body.topic})
    return {"ok": True, "topic": body.topic}


@app.post("/api/sessions/{session_id}/transcript")
async def api_set_transcript(session_id: str, body: TranscriptBody):
    db.update_session_transcript(session_id, body.transcript)
    await _emit_to_session(session_id, "transcript_updated", {"transcript": body.transcript})
    return {"ok": True}


@app.post("/api/sessions/{session_id}/escalation")
async def api_add_escalation(session_id: str, body: EscalationBody):
    entry = db.add_escalation(session_id, body.student_id, body.tag, body.query)
    await _emit_to_session(session_id, "escalation_added", entry)
    return {"ok": True, "escalation": entry}


@app.get("/api/sessions/{session_id}/escalations")
def api_get_escalations(session_id: str):
    return db.get_escalations(session_id)


# ──────────────────────────────────────────────
# Recall.ai transcript ingestion (Issue #2 bridge)
# ──────────────────────────────────────────────

_rolling_transcripts: dict[str, list[str]] = {}

@app.post("/api/recall/transcript")
async def api_recall_transcript(body: RecallTranscriptBody):
    session_id = body.session_id
    speaker = body.speaker
    text = body.text
    is_final = body.is_final

    if not text.strip():
        return {"ok": True, "skipped": "empty"}

    if session_id not in _rolling_transcripts:
        s = db.get_session(session_id)
        existing = s["transcript"] if s and s["transcript"] else ""
        _rolling_transcripts[session_id] = [existing] if existing else []

    if is_final:
        line = f"{speaker}: {text}"
        _rolling_transcripts[session_id].append(line)
        full_transcript = "\n".join(_rolling_transcripts[session_id])
        db.update_session_transcript(session_id, full_transcript)
        await _emit_to_session(session_id, "transcript_updated", {"transcript": full_transcript})
        print(f"[recall] {speaker}: {text}  (session {session_id})")
    else:
        current = "\n".join(_rolling_transcripts[session_id])
        preview = f"{current}\n{speaker}: {text} ..."
        await _emit_to_session(session_id, "transcript_updated", {"transcript": preview})

    return {"ok": True}


# ──────────────────────────────────────────────
# Backward-compat: old single-session endpoints
# ──────────────────────────────────────────────

@app.get("/api/state")
def api_state_compat():
    snap = _session_snapshot("session-001")
    if not snap:
        return {"topic": "", "transcript": "", "escalations": [], "updated_at": _now_iso()}
    return {
        "topic": snap["topic"],
        "transcript": snap["transcript"],
        "escalations": snap["escalations"],
        "updated_at": snap["updated_at"],
    }


@app.post("/api/topic")
async def api_topic_compat(body: TopicBody):
    db.update_session_topic("session-001", body.topic)
    await _emit_to_session("session-001", "topic_updated", {"topic": body.topic})
    return {"ok": True, "topic": body.topic}


@app.post("/api/transcript")
async def api_transcript_compat(body: TranscriptBody):
    db.update_session_transcript("session-001", body.transcript)
    await _emit_to_session("session-001", "transcript_updated", {"transcript": body.transcript})
    return {"ok": True}


@app.post("/api/escalation")
async def api_escalation_compat(body: EscalationBody):
    entry = db.add_escalation("session-001", "anonymous", body.tag)
    await _emit_to_session("session-001", "escalation_added", entry)
    return {"ok": True}


# ──────────────────────────────────────────────
# WebSocket endpoint
# Client connects to /ws/{session_id}
# Receives JSON: { "event": "...", ...payload }
# Can send JSON commands:
#   { "action": "set_topic", "topic": "..." }
#   { "action": "set_transcript", "transcript": "..." }
#   { "action": "add_escalation", "tag": "...", "student_id": "...", "query": "..." }
#   { "action": "request_state" }
# ──────────────────────────────────────────────

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    print(f"[ws] client connected to room {session_id}")

    # Send initial state
    snap = _session_snapshot(session_id)
    if snap:
        await websocket.send_text(json.dumps({"event": "session_state", **snap}))

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            action = data.get("action", "")

            if action == "set_topic":
                topic = data.get("topic", "")
                db.update_session_topic(session_id, topic)
                await _emit_to_session(session_id, "topic_updated", {"topic": topic})
                print(f"[ws] topic → {topic!r}  (session {session_id})")

            elif action == "set_transcript":
                transcript = data.get("transcript", "")
                db.update_session_transcript(session_id, transcript)
                await _emit_to_session(session_id, "transcript_updated", {"transcript": transcript})

            elif action == "add_escalation":
                tag = data.get("tag", "")
                student_id = data.get("student_id", "anonymous")
                query = data.get("query", "")
                entry = db.add_escalation(session_id, student_id, tag, query)
                await _emit_to_session(session_id, "escalation_added", entry)
                print(f"[ws] escalation → {tag!r}  (session {session_id})")

            elif action == "request_state":
                snap = _session_snapshot(session_id)
                if snap:
                    await websocket.send_text(json.dumps({"event": "session_state", **snap}))

    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)
        print(f"[ws] client disconnected from room {session_id}")


# ──────────────────────────────────────────────
# Entrypoint
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 5001))
    print(f"🚀  QnAI session server starting on :{port}")
    print(f"📦  Database at {db.DB_PATH}")
    print(f"👥  Users: {len(db.list_users())}")
    print(f"📚  Sessions: {len(db.list_sessions())}")
    uvicorn.run(app, host="0.0.0.0", port=port)
