from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from . import db
from .recall_router import manager

router = APIRouter(prefix="/api/users", tags=["users"])

class UserJoin(BaseModel):
    name: str
    role: str
    session_id: str

@router.post("/join")
async def user_join(user_data: UserJoin):
    # Check if session exists
    session_obj = db.get_session(user_data.session_id)
    if not session_obj:
        # For hackathon convenience, if session doesn't exist, we'll allow joining session-001
        if user_data.session_id == "session-001":
            pass 
        else:
            raise HTTPException(status_code=404, detail="Session not found")
        
    # In this simple SQLite version, we'll just return a mock user ID 
    # or you can add a db.add_user function if you want full persistence.
    # For now, let's just broadcast the join.
    
    await manager.broadcast({
        "type": "user_joined",
        "user": {"name": user_data.name, "role": user_data.role}
    })
    
    return {"id": 999, "name": user_data.name, "role": user_data.role}
