from fastapi import FastAPI
from app.api import student, teacher

app = FastAPI()

app.include_router(student.router, prefix="/student")
app.include_router(teacher.router, prefix="/teacher")