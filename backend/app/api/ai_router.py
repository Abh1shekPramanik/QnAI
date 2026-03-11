import os
import google.generativeai as genai
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from . import db
from .recall_router import manager

router = APIRouter(prefix="/api/ai", tags=["ai"])

class AnswerRequest(BaseModel):
    session_id: str
    question_id: int

@router.post("/answer")
async def answer_question(req: AnswerRequest):
    # HARDCODED TEST RESPONSE
    mock_answer = "A Binary Search Tree (BST) is a tree-like data structure where each node has at most two children. For any given node, all elements in the left subtree are smaller, and all elements in the right subtree are larger. This allows for very fast searching, insertion, and deletion."
    
    conn = db.get_conn()
    try:
        # Check if question exists
        q_row = conn.execute("SELECT * FROM escalations WHERE id = ?", (req.question_id,)).fetchone()
        if not q_row:
            conn.close()
            raise HTTPException(status_code=404, detail="Question not found")

        # Update DB
        conn.execute("UPDATE escalations SET query = ? WHERE id = ?", 
                    (f"{q_row['query']}\n\nAI Answer: {mock_answer}", req.question_id))
        conn.commit()
        conn.close()

        # Broadcast to everyone via WebSocket
        await manager.broadcast({
            "type": "ai_answer",
            "question_id": req.question_id,
            "answer": mock_answer
        })
        
        return {"answer": mock_answer}
    except Exception as e:
        if conn: conn.close()
        print(f"❌ MOCK AI ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
