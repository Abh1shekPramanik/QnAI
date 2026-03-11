import os
import json
import httpx
from datetime import datetime
from typing import List, Dict
from fastapi import APIRouter, Request, HTTPException, WebSocket, WebSocketDisconnect
from . import db

router = APIRouter(prefix="/api/recall", tags=["recall"])

RECALL_API_KEY = os.getenv("RECALL_API_KEY")
RECALL_REGION = os.getenv("RECALL_REGION", "us-west-2")
RECALL_BASE_URL = f"https://{RECALL_REGION}.recall.ai/api/v1"

# Track the current active transcript ID for each participant to keep updates stable
active_transcript_ids: Dict[int, str] = {}

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                continue

manager = ConnectionManager()

@router.post("/join")
async def join_meeting(meeting_url: str, session_id: str = "session-001"):
    headers = {
        "Authorization": f"Token {RECALL_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "meeting_url": meeting_url.strip(),
        "bot_name": "QnAI Assistant",
        "recording_config": {
            "transcript": {
                "provider": {
                    "recallai_streaming": { 
                        "mode": "prioritize_low_latency",
                        "language_code": "en" 
                    }
                }
            },
            "realtime_endpoints": [
                {
                    "url": os.getenv("RECALL_WEBHOOK_URL"),
                    "type": "webhook",
                    "events": ["transcript.data", "transcript.partial_data"]
                }
            ]
        }
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{RECALL_BASE_URL}/bot/", json=payload, headers=headers)
        if response.status_code != 201:
            raise HTTPException(status_code=response.status_code, detail=f"Recall failed: {response.text}")
        bot_data = response.json()
        db.update_session_bot_id(session_id, bot_data["id"], meeting_url)
        return {"session_id": session_id, "bot_id": bot_data["id"]}

@router.post("/webhook")
async def recall_webhook(request: Request):
    body = await request.json()
    event = body.get("event")
    data = body.get("data", {})
    bot_id = data.get("bot", {}).get("id")
    
    if event in ["transcript.data", "transcript.partial_data"]:
        inner_data = data.get("data", {})
        participant = inner_data.get("participant", {})
        participant_id = participant.get("id")
        words = inner_data.get("words", [])
        text_content = " ".join([w.get("text", "") for w in words])
        
        # 1. Determine the stable ID for this sentence
        # Recall provides a real ID in body["data"]["transcript"]["id"]
        t_id = data.get("transcript", {}).get("id")
        
        # Fallback if Recall ID is missing (common in some partial events)
        if not t_id:
            if event == "transcript.partial_data":
                # Use a persistent ID for the "current" partial of this speaker
                if participant_id not in active_transcript_ids:
                    active_transcript_ids[participant_id] = f"active-{participant_id}-{datetime.now().timestamp()}"
                t_id = active_transcript_ids[participant_id]
            else:
                t_id = f"final-{datetime.now().timestamp()}"

        # 2. If it's finalized, save to DB and clear the active ID tracker
        if event == "transcript.data":
            session_obj = db.get_session_by_bot_id(bot_id)
            if session_obj:
                db.save_transcript(session_obj["id"], participant.get("name", "Unknown"), text_content, True)
            if participant_id in active_transcript_ids:
                del active_transcript_ids[participant_id]
            
        # 3. Broadcast to frontend
        await manager.broadcast({
            "type": "transcript",
            "id": t_id,
            "speaker": participant.get("name", "Unknown"),
            "text": text_content,
            "is_final": (event == "transcript.data")
        })
        
    return {"status": "ok"}

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
