from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime, timezone

router = APIRouter(tags=["topic"])

class TopicUpdate(BaseModel):
    topic: str = Field(..., min_length=1, max_length=300)

class TopicResponse(BaseModel):
    topic: str
    updated_at: str
    updated_by: str

_current_topic: dict = {
    "topic": "",
    "updated_at": "",
    "updated_by": "teacher",
}

@router.get("/", response_model=TopicResponse)
async def get_topic():
    if not _current_topic["topic"]:
        raise HTTPException(status_code=404, detail="No topic set")
    return _current_topic

@router.put("/", response_model=TopicResponse)
async def set_topic(body: TopicUpdate):
    _current_topic["topic"] = body.topic.strip()
    _current_topic["updated_at"] = datetime.now(timezone.utc).isoformat()
    _current_topic["updated_by"] = "teacher"
    return _current_topic
