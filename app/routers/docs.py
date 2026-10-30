"""Docs mode: upload documents, chat with them, get cited answers."""
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app import database as db
from app.llm import chat_stream
from app.rag import chunk_text, embed, extract_pdf, extract_text_file, ollama_ok, retrieve

router = APIRouter(prefix="/api/docs", tags=["docs"])

SYSTEM_PROMPT = """You answer questions using ONLY the context below.
Cite every factual claim with the source number, like [1] or [2].
If the answer is not in the context, say "I don't know based on your documents."
Do not invent facts."""


class AskBody(BaseModel):
    question: str
    doc_ids: list[int] | None = None
    chat_id: int | None = None


def read_upload(filename, data):
    name = filename.lower()
    if name.endswith(".pdf"):
        return extract_pdf(data)
    if name.endswith((".txt", ".md", ".markdown")):
        return extract_text_file(data)
    raise HTTPException(400, "Only PDF, TXT and Markdown files are supported.")


@router.post("/upload")
def upload(file: UploadFile):
    data = file.file.read()
    text = read_upload(file.filename, data)
    if not text.strip():
        raise HTTPException(400, "No readable text found in that file.")
    chunks = chunk_text(text)
    try:
        vectors = embed(chunks)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    doc_id = db.add_document("docs", file.filename)
    db.add_chunks(doc_id, chunks, vectors)
    return {"doc_id": doc_id, "name": file.filename, "chunks": len(chunks)}


@router.get("/documents")
def documents():
    return db.list_documents("docs")


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: int):
    db.delete_document(doc_id)
    return {"deleted": doc_id}


@router.post("/ask")
def ask(body: AskBody):
    chunks = db.get_chunks("docs", body.doc_ids)
    if not chunks:
        raise HTTPException(400, "Upload a document first.")
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
        "docs", body.question[:40] or "New chat"
    )
    db.add_message(chat_id, "user", body.question)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {body.question}"},
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
    return db.list_chats("docs")


@router.get("/chats/{chat_id}")
def chat_history(chat_id: int):
    return db.get_messages(chat_id)
