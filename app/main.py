"""PrivateAI Studio: every private AI tool in one place, 100% offline.

Modes: Docs, Code, Resume, Meetings, Notes. All AI runs through Ollama
on your own machine. Nothing is uploaded anywhere.
"""
import os

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import database as db
from app.rag import ollama_ok
from app.routers import code, docs, meetings, notes, resume

app = FastAPI(title="PrivateAI Studio")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")


@app.on_event("startup")
def startup():
    db.init_db()


app.include_router(docs.router)
app.include_router(code.router)
app.include_router(resume.router)
app.include_router(meetings.router)
app.include_router(notes.router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/api/health")
def health():
    return {"ollama": ollama_ok()}


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
