from fastapi import APIRouter
from pydantic import BaseModel
from app.api.student import escalated_tags

router = APIRouter()

current_topic = {"topic": ""}

class TopicUpdate(BaseModel):
    topic: str

@router.get("/tags")
async def get_tags():
    return {
        "tags": escalated_tags,
        "count": len(escalated_tags)
    }

@router.post("/topic")
async def set_topic(payload: TopicUpdate):
    current_topic["topic"] = payload.topic
    return {"status": "topic updated", "topic": payload.topic}

@router.get("/topic")
async def get_topic():
    return current_topic

@router.delete("/tags/clear")
async def clear_tags():
    escalated_tags.clear()
    return {"status": "cleared"}