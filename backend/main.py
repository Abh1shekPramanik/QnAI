import os
import json
import asyncio
import httpx
from typing import List
from datetime import datetime, timezone
from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

app = FastAPI()

# ── Credentials ───────────────────────────────────────────────────
RECALL_API_KEY  = os.getenv("RECALL_API_KEY")
RECALL_REGION   = os.getenv("RECALL_REGION", "us-west-2")
RECALL_BASE_URL = f"https://{RECALL_REGION}.recall.ai/api/v1"

GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-2.0-flash")

# ── Rolling transcript buffer ─────────────────────────────────────
# session_id → list of final transcript strings
_transcript_buffer: dict[str, list[str]] = {}
_last_extraction:   dict[str, float]     = {}   # session_id → timestamp
EXTRACTION_INTERVAL = 60                         # seconds between Gemini calls


# ── Gemini context extraction ─────────────────────────────────────

async def extract_and_store_context(session_id: str) -> None:
    """
    Take the last 5 min of transcript for this session,
    send it to Gemini, and store the result back in SQLite.
    """
    chunks = _transcript_buffer.get(session_id, [])
    if not chunks:
        return

    # Keep only last 50 chunks (approx 5 min)
    recent_text = " ".join(chunks[-50:])
    if len(recent_text.strip()) < 20:
        return

    prompt = f"""You are a lecture transcript analyzer.
Given this transcript excerpt, extract:
1. current_subtopic — the specific concept being discussed right now
2. key_terms — list of technical terms the professor emphasized
3. summary — 1-2 sentence plain-English summary of what was just covered

Respond ONLY in valid JSON, no markdown:
{{"current_subtopic": "string", "key_terms": ["string"], "summary": "string"}}

TRANSCRIPT:
{recent_text}"""

    try:
        response = await gemini_model.generate_content_async(
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            generation_config=genai.GenerationConfig(max_output_tokens=300, temperature=0.3),
        )
        raw = response.text.strip().replace("```json", "").replace("```", "").strip()
        context = json.loads(raw)

        # Store back into SQLite so sync_pages / frontend can read it
        from app.api.db import update_session_transcript
        update_session_transcript(session_id, json.dumps({
            "raw": recent_text,
            "context": context,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }))

        print(f"[Gemini] [{session_id}] subtopic: {context.get('current_subtopic', '')[:60]}")

    except Exception as e:
        print(f"[Gemini] [{session_id}] extraction failed: {e}")


# ── Connection Manager for broadcasting to frontend ───────────────

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


# ── Routes ────────────────────────────────────────────────────────

@app.get("/")
def read_root():
    return {"status": "Recall.ai Backend Running"}


# 1. Start a Bot — provide a Zoom URL + session_id
@app.post("/recall/join/{session_id}")
async def join_meeting(session_id: str, meeting_url: str):
    """
    Deploy the Recall bot into a Zoom meeting, linked to a session.
    session_id stored as bot metadata so the webhook knows
    which session to write transcripts to.
    """
    headers = {
        "Authorization": f"Token {RECALL_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "meeting_url": meeting_url.strip(),
        "bot_name": "Q&AI Bot",
        "metadata": {"session_id": session_id},   # links bot → session
        "recording_config": {
            "transcript": {
                "provider": {
                    "recallai_streaming": {
                        "mode": "prioritize_low_latency",
                        "language_code": "en",
                    }
                }
            },
            "realtime_endpoints": [
                {
                    "url": os.getenv("RECALL_WEBHOOK_URL"),
                    "type": "webhook",
                    "events": ["transcript.data", "transcript.partial_data"],
                }
            ],
        },
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(f"{RECALL_BASE_URL}/bot/", json=payload, headers=headers)

    if response.status_code != 201:
        raise HTTPException(status_code=response.status_code, detail=f"Recall failed: {response.text}")

    # Initialise buffer for this session
    _transcript_buffer.setdefault(session_id, [])
    _last_extraction[session_id] = 0.0

    return response.json()


# 2. Webhook — Recall posts live transcripts here
@app.post("/recall/webhook")
async def recall_webhook(request: Request):
    try:
        body  = await request.json()
        event = body.get("event")
        data  = body.get("data", {})

        if event in ["transcript.data", "transcript.partial_data"]:
            inner_data   = data.get("data", {})
            participant  = inner_data.get("participant", {})
            words        = inner_data.get("words", [])
            text_content = " ".join([w.get("text", "") for w in words])
            is_final     = (event == "transcript.data")

            transcript_data = {
                "speaker":    participant.get("name", "Unknown"),
                "text":       text_content,
                "is_final":   is_final,
                "event_type": event,
            }

            # Broadcast to all connected frontend clients (unchanged)
            await manager.broadcast(json.dumps(transcript_data))

            prefix = "[FINAL]" if is_final else "[PARTIAL]"
            print(f"{prefix} {transcript_data['speaker']}: {transcript_data['text']}")

            # ── Buffer final chunks + trigger Gemini every 60s ──────
            if is_final and text_content.strip():
                session_id = (data.get("metadata") or {}).get("session_id")

                if session_id:
                    # Append to rolling buffer
                    _transcript_buffer.setdefault(session_id, []).append(text_content.strip())

                    # Trigger Gemini extraction if 60s have passed
                    now  = asyncio.get_event_loop().time()
                    last = _last_extraction.get(session_id, 0.0)
                    if now - last >= EXTRACTION_INTERVAL:
                        _last_extraction[session_id] = now
                        asyncio.create_task(extract_and_store_context(session_id))

        return {"status": "ok"}

    except Exception as e:
        print(f"Error processing webhook: {e}")
        return {"status": "error", "message": str(e)}


# 3. WebSocket — frontend listens for live transcript stream
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