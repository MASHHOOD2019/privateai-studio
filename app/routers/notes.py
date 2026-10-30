"""Notes mode: private notes, AES-encrypted at rest.

The password is never stored. Each request carries it, the server derives
a key with PBKDF2 and decrypts in memory only.
"""
import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import database as db

router = APIRouter(prefix="/api/notes", tags=["notes"])

SALT = b"privateai-studio-notes-v1"


def make_fernet(password):
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=SALT,
        iterations=600_000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return Fernet(key)


class NoteCreate(BaseModel):
    title: str
    content: str
    password: str


class NoteOpen(BaseModel):
    password: str


@router.post("")
def create_note(body: NoteCreate):
    if not body.password:
        raise HTTPException(400, "A password is required.")
    token = make_fernet(body.password).encrypt(body.content.encode()).decode()
    note_id = db.add_note(body.title, token)
    return {"id": note_id, "title": body.title}


@router.get("")
def list_notes():
    return db.list_notes()


@router.post("/{note_id}/open")
def open_note(note_id: int, body: NoteOpen):
    token = db.get_note_body(note_id)
    if token is None:
        raise HTTPException(404, "Note not found.")
    try:
        content = make_fernet(body.password).decrypt(token.encode()).decode()
    except InvalidToken:
        raise HTTPException(401, "Wrong password.")
    return {"id": note_id, "content": content}


@router.delete("/{note_id}")
def delete_note(note_id: int):
    db.delete_note(note_id)
    return {"deleted": note_id}
