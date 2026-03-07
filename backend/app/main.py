import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import topic_router, recall_router, session_router, ai_router, user_router

app = FastAPI(title="QnAI API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(topic_router.router, prefix="/api/topic")
app.include_router(recall_router.router)
app.include_router(session_router.router)
app.include_router(ai_router.router)
app.include_router(user_router.router)

@app.get("/")
async def root():
    return {"message": "QnAI Backend is running!"}
