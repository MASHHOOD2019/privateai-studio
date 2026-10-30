"""Resume mode: honest, offline feedback of a CV against a job description."""
from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.llm import chat_stream
from app.rag import ollama_ok
from app.routers.docs import read_upload

router = APIRouter(prefix="/api/resume", tags=["resume"])

SYSTEM_PROMPT = """You are an honest resume coach. Compare the CV against the job
description below. Be direct and specific:
1. Matches: skills and experience that fit, with evidence from the CV.
2. Gaps: what the job asks for that the CV does not show.
3. Three concrete fixes, each one sentence.
No flattery, no invented experience. If the CV is weak for this job, say so."""


@router.post("/analyze")
def analyze(cv: UploadFile, job_description: str = Form(...)):
    if not ollama_ok():
        raise HTTPException(
            503,
            "Ollama is not reachable. Start Ollama, then run: ollama pull llama3.1",
        )
    text = read_upload(cv.filename, cv.file.read())
    if not text.strip():
        raise HTTPException(400, "No readable text found in that CV.")
    if not job_description.strip():
        raise HTTPException(400, "Paste the job description.")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"CV:\n{text[:12000]}\n\nJob description:\n{job_description[:8000]}",
        },
    ]
    return StreamingResponse(chat_stream(messages), media_type="text/plain")
