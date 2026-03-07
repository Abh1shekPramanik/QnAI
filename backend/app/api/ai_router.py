import os
from google import genai
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from . import db

router = APIRouter(prefix="/api/ai", tags=["ai"])

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

MODEL = "gemini-2.5-flash"

class AnswerRequest(BaseModel):
    session_id: str
    question_id: int

@router.post("/answer")
async def answer_question(req: AnswerRequest):
    if not client:
        raise HTTPException(status_code=500, detail="Gemini API Key not configured")

    # 1. Get the question
    conn = db.get_conn()
    q_row = conn.execute("SELECT * FROM escalations WHERE id = ?", (req.question_id,)).fetchone()

    if not q_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Question not found")

    question_text = q_row["query"] or q_row["tag"]

    # 2. Get recent transcripts for context
    transcripts = db.get_transcripts(req.session_id)
    context = "\n".join([f"{t['speaker']}: {t['text']}" for t in transcripts[-20:]])

    # 3. Generate Answer using new SDK
    prompt = f"""
    You are an AI assistant in a live university lecture. 
    Based on the following recent transcript of the lecture, answer the student's question concisely.
    
    Lecture Context:
    {context}
    
    Student Question:
    {question_text}
    
    AI Answer:
    """

    try:
        response = client.models.generate_content(model=MODEL, contents=prompt)
        answer = response.text.strip()

        # 4. Save answer to DB
        conn.execute("UPDATE escalations SET query = ? WHERE id = ?",
                    (f"{question_text}\n\nAI Answer: {answer}", req.question_id))
        conn.commit()
        conn.close()

        return {"answer": answer}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))