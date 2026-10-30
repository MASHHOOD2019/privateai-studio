"""Meetings mode: turn a transcript into summary, decisions and actions."""
from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.llm import chat_stream
from app.rag import ollama_ok

router = APIRouter(prefix="/api/meetings", tags=["meetings"])

SYSTEM_PROMPT = """You turn meeting transcripts into useful notes. Reply with exactly
these sections:
Summary: two or three sentences on what the meeting was about.
Decisions: bullet list of what was decided.
Action items: bullet list, each with an owner if one was named.
Open questions: bullet list of what was left unresolved.
Use only what the transcript says. Do not invent names or decisions."""


@router.post("/summarize")
def summarize(
    file: UploadFile | None = None, transcript: str = Form(default="")
):
    if not ollama_ok():
        raise HTTPException(
            503,
            "Ollama is not reachable. Start Ollama, then run: ollama pull llama3.1",
        )
    text = ""
    if file is not None:
        text = file.file.read().decode("utf-8", errors="replace")
    elif transcript.strip():
        text = transcript
    if not text.strip():
        raise HTTPException(400, "Upload or paste a meeting transcript.")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Transcript:\n{text[:15000]}"},
    ]
    return StreamingResponse(chat_stream(messages), media_type="text/plain")
