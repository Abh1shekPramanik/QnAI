"""
QnAI — FastAPI entry point
Run:  uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.topic_router import router as topic_router

app = FastAPI(title="QnAI API", version="0.1.0")

# Allow the Vite dev server (port 5173) and Vercel production URL
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        # Add your Vercel production URL here when deployed (Issue #10)
        # "https://qnai.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(topic_router)


@app.get("/health")
async def health():
    return {"status": "ok"}