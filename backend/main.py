import os
import json
import httpx
from typing import List
from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Credentials
RECALL_API_KEY = os.getenv("RECALL_API_KEY")
RECALL_REGION = os.getenv("RECALL_REGION", "us-west-2")  # Default to us-west-2
RECALL_BASE_URL = f"https://{RECALL_REGION}.recall.ai/api/v1"

# Connection Manager for Broad-casting to Frontend
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                self.active_connections.remove(connection)

manager = ConnectionManager()

@app.get("/")
def read_root():
    return {"status": "Recall.ai Backend Running"}

# 1. Start a Bot: Provide a Zoom URL to have a bot join
@app.post("/recall/join")
async def join_meeting(meeting_url: str):
    headers = {
        "Authorization": f"Token {RECALL_API_KEY}",
        "Content-Type": "application/json"
    }
    
    meeting_url = meeting_url.strip()
    
    # Correct Recall v1 Nested Schema
    payload = {
        "meeting_url": meeting_url,
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
            
        return response.json()

# 2. Webhook Handler: Recall sends live transcripts here
@app.post("/recall/webhook")
async def recall_webhook(request: Request):
    try:
        body = await request.json()
        event = body.get("event")
        data = body.get("data", {})
        
        # Recall.ai v1 uses 'transcript.data' (final) and 'transcript.partial_data' (partial)
        if event in ["transcript.data", "transcript.partial_data"]:
            # Based on raw logs, the structure is: body["data"]["data"]
            inner_data = data.get("data", {})
            participant = inner_data.get("participant", {})
            words = inner_data.get("words", [])
            
            # Join the words list into a single string
            text_content = " ".join([w.get("text", "") for w in words])
            
            transcript_data = {
                "speaker": participant.get("name", "Unknown"),
                "text": text_content,
                "is_final": (event == "transcript.data"),
                "event_type": event
            }
            
            # Broadcast to all connected frontend clients
            await manager.broadcast(json.dumps(transcript_data))
            
            # Print to console for debugging
            prefix = "[FINAL]" if transcript_data["is_final"] else "[PARTIAL]"
            print(f"{prefix} {transcript_data['speaker']}: {transcript_data['text']}")
            
        return {"status": "ok"}
    except Exception as e:
        print(f"Error processing webhook: {e}")
        # Always return 200 to Recall to avoid excessive retries, 
        # unless it's a critical infrastructure failure.
        return {"status": "error", "message": str(e)}

# 3. WebSocket: For Frontend/Teammates to listen to the live stream
@app.websocket("/ws/transcripts")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
