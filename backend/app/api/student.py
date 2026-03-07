from fastapi import APIRouter
from pydantic import BaseModel
from app.utils.gemini import get_ai_answer, compress_query

router = APIRouter()

# In-memory store for escalated tags
escalated_tags = []

class StudentQuery(BaseModel):
    query: str
    topic: str
    transcript: str

class EscalateQuery(BaseModel):
    query: str

@router.post("/ask")
async def ask_ai(payload: StudentQuery):
    answer = get_ai_answer(
        query=payload.query,
        topic=payload.topic,
        transcript=payload.transcript
    )
    return {"answer": answer}


@router.post("/escalate")
async def escalate(payload: EscalateQuery):
    tag = compress_query(payload.query)
    escalated_tags.append(tag)
    return {"tag": tag, "status": "escalated"}