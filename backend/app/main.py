import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import topic_router, recall_router, session_router, ai_router, user_router, student_router, teacher_router
from .services import context_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("qnai")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("QnAI backend starting up")
    yield
    # Shutdown
    logger.info("QnAI backend shutting down — stopping all extraction tasks")
    context_service.stop_all()


app = FastAPI(title="QnAI API", lifespan=lifespan)

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
app.include_router(student_router.router)
app.include_router(teacher_router.router)

@app.get("/")
async def root():
    return {"message": "QnAI Backend is running!"}