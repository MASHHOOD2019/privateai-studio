"""Code mode: upload a repo zip, ask questions about the codebase."""
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app import database as db
from app.llm import chat_stream
from app.rag import chunk_text, embed, extract_code_zip, ollama_ok, retrieve

router = APIRouter(prefix="/api/code", tags=["code"])

SYSTEM_PROMPT = """You are a codebase guide. Answer using ONLY the code excerpts below.
Reference file paths when you mention code, like "in app/main.py".
If the answer is not in the excerpts, say "I couldn't find that in this codebase."
Do not invent files or functions."""


class AskBody(BaseModel):
    question: str
    doc_ids: list[int] | None = None
    chat_id: int | None = None


@router.post("/upload")
def upload(file: UploadFile):
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "Upload a zip of the codebase.")
    text = extract_code_zip(file.file.read())
    if not text.strip():
        raise HTTPException(400, "No code files found in that zip.")
    chunks = chunk_text(text, size=1200, overlap=150)
    try:
        vectors = embed(chunks)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    doc_id = db.add_document("code", file.filename)
    db.add_chunks(doc_id, chunks, vectors)
    return {"doc_id": doc_id, "name": file.filename, "chunks": len(chunks)}


@router.get("/documents")
def documents():
    return db.list_documents("code")


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: int):
    db.delete_document(doc_id)
    return {"deleted": doc_id}


@router.post("/ask")
def ask(body: AskBody):
    chunks = db.get_chunks("code", body.doc_ids)
    if not chunks:
        raise HTTPException(400, "Upload a codebase zip first.")
    if not ollama_ok():
        raise HTTPException(
            503,
            "Ollama is not reachable. Start Ollama, then run: ollama pull llama3.1",
        )
    try:
        top = retrieve(body.question, chunks)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    context = "\n\n".join(
        f"[{i + 1}] ({c['doc_name']})\n{c['text']}" for i, c in enumerate(top)
    )
    sources = "\n".join(
        f"[{i + 1}] {c['doc_name']}: {c['text'][:120].replace(chr(10), ' ')}..."
        for i, c in enumerate(top)
    )
    chat_id = body.chat_id or db.add_chat(
        "code", body.question[:40] or "New chat"
    )
    db.add_message(chat_id, "user", body.question)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Code excerpts:\n{context}\n\nQuestion: {body.question}"},
    ]

    def generate():
        full = []
        try:
            for delta in chat_stream(messages):
                full.append(delta)
                yield delta
            yield f"\n\nSources:\n{sources}"
            full.append(f"\n\nSources:\n{sources}")
        finally:
            db.add_message(chat_id, "assistant", "".join(full))

    return StreamingResponse(generate(), media_type="text/plain")


@router.get("/chats")
def chats():
    return db.list_chats("code")


@router.get("/chats/{chat_id}")
def chat_history(chat_id: int):
    return db.get_messages(chat_id)
