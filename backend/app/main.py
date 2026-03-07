from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import student, teacher

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(student.router, prefix="/student")
app.include_router(teacher.router, prefix="/teacher")