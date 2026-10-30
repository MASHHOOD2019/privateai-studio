"""Retrieval-Augmented Generation helpers.

- chunk_text: split text into overlapping chunks
- embed: embeddings via Ollama (nomic-embed-text)
- retrieve: cosine-similarity search over stored chunks
- extractors: PDF, plain text, code zips
"""
import io
import json
import math
import os
import zipfile

import httpx
from pypdf import PdfReader

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".c", ".cpp", ".h", ".hpp",
    ".java", ".go", ".rs", ".rb", ".php", ".cs", ".swift", ".kt",
    ".html", ".css", ".scss", ".sql", ".sh", ".yaml", ".yml", ".json",
}


def chunk_text(text, size=800, overlap=100):
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def ollama_ok():
    try:
        r = httpx.get(OLLAMA_URL + "/api/tags", timeout=3, trust_env=False)
        return r.status_code == 200
    except Exception:
        return False


def embed(texts):
    """Embed a list of texts with Ollama. Raises RuntimeError if unreachable."""
    try:
        out = []
        for text in texts:
            r = httpx.post(
                OLLAMA_URL + "/api/embeddings",
                json={"model": EMBED_MODEL, "prompt": text},
                timeout=120,
                trust_env=False,
            )
            r.raise_for_status()
            out.append(r.json()["embedding"])
        return out
    except Exception as exc:
        raise RuntimeError(
            "Ollama is not reachable. Start Ollama, then run: "
            f"ollama pull {EMBED_MODEL}"
        ) from exc


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if not na or not nb:
        return 0.0
    return dot / (na * nb)


def retrieve(query, chunks, top_k=4):
    """Return the top_k chunks most similar to the query."""
    query_vec = embed([query])[0]
    scored = []
    for chunk in chunks:
        vec = json.loads(chunk["embedding"])
        scored.append((cosine(query_vec, vec), chunk))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [chunk for _, chunk in scored[:top_k]]


def extract_pdf(data):
    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def extract_text_file(data):
    return data.decode("utf-8", errors="replace")


def extract_code_zip(data):
    """Extract code files from a zip, prefixing each chunk with its path."""
    texts = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            _, ext = os.path.splitext(info.filename)
            if ext.lower() not in CODE_EXTENSIONS:
                continue
            if info.file_size > 200_000:
                continue
            try:
                content = archive.read(info.filename).decode("utf-8", errors="replace")
            except Exception:
                continue
            texts.append(f"File: {info.filename}\n{content}")
    return "\n\n".join(texts)
