import os
import json
import httpx
from typing import List
from fastapi import APIRouter, Request, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from pydantic import BaseModel
from . import db

router = APIRouter(prefix="/api/recall", tags=["recall"])

RECALL_API_KEY = os.getenv("RECALL_API_KEY")
RECALL_REGION = os.getenv("RECALL_REGION", "us-west-2")
RECALL_BASE_URL = f"https://{RECALL_REGION}.recall.ai/api/v1"

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                self.active_connections.remove(connection)

manager = ConnectionManager()

@router.post("/join")
async def join_meeting(meeting_url: str, session_id: str = "session-001"):
    headers = {
        "Authorization": f"Token {RECALL_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "meeting_url": meeting_url.strip(),
        "bot_name": "QnAI Transcript Bot",
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
        
        # Update session with bot_id
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
        words = inner_data.get("words", [])
        text_content = " ".join([w.get("text", "") for w in words])
        
        # Find session
        session_obj = db.get_session_by_bot_id(bot_id)
        if session_obj and event == "transcript.data":
            db.save_transcript(session_obj["id"], participant.get("name", "Unknown"), text_content, True)
            
        # Broadcast via WebSocket
        payload = {
            "type": "transcript",
            "speaker": participant.get("name", "Unknown"),
            "text": text_content,
            "is_final": (event == "transcript.data")
        }
        await manager.broadcast(payload)
        
    return {"status": "ok"}

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
