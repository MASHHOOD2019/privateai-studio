"""SQLite storage for PrivateAI Studio.

Tables:
- documents: uploaded files, tagged by mode (docs, code)
- chunks: text chunks with embeddings (stored as JSON)
- chats / messages: conversation history per mode
- notes: Fernet-encrypted private notes
"""
import os
import sqlite3
import time

DB_PATH = os.environ.get("PRIVATEAI_DB", "privateai.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS documents(
            id INTEGER PRIMARY KEY,
            mode TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS chunks(
            id INTEGER PRIMARY KEY,
            doc_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            embedding TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS chats(
            id INTEGER PRIMARY KEY,
            mode TEXT NOT NULL,
            title TEXT NOT NULL,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages(
            id INTEGER PRIMARY KEY,
            chat_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS notes(
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at REAL NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()


def add_document(mode, name):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO documents(mode, name, created_at) VALUES (?, ?, ?)",
        (mode, name, time.time()),
    )
    doc_id = cur.lastrowid
    conn.commit()
    conn.close()
    return doc_id


def add_chunks(doc_id, texts, embeddings):
    import json

    conn = get_db()
    conn.executemany(
        "INSERT INTO chunks(doc_id, text, embedding) VALUES (?, ?, ?)",
        [(doc_id, t, json.dumps(e)) for t, e in zip(texts, embeddings)],
    )
    conn.commit()
    conn.close()


def get_chunks(mode, doc_ids=None):
    conn = get_db()
    if doc_ids:
        placeholders = ",".join("?" for _ in doc_ids)
        rows = conn.execute(
            f"""SELECT chunks.id, chunks.doc_id, chunks.text, chunks.embedding,
                       documents.name AS doc_name
                FROM chunks JOIN documents ON chunks.doc_id = documents.id
                WHERE documents.mode = ? AND documents.id IN ({placeholders})""",
            [mode, *doc_ids],
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT chunks.id, chunks.doc_id, chunks.text, chunks.embedding,
                      documents.name AS doc_name
               FROM chunks JOIN documents ON chunks.doc_id = documents.id
               WHERE documents.mode = ?""",
            [mode],
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_documents(mode):
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, created_at FROM documents WHERE mode = ? ORDER BY id DESC",
        [mode],
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_document(doc_id):
    conn = get_db()
    conn.execute("DELETE FROM chunks WHERE doc_id = ?", [doc_id])
    conn.execute("DELETE FROM documents WHERE id = ?", [doc_id])
    conn.commit()
    conn.close()


def add_chat(mode, title):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO chats(mode, title, created_at) VALUES (?, ?, ?)",
        (mode, title, time.time()),
    )
    chat_id = cur.lastrowid
    conn.commit()
    conn.close()
    return chat_id


def add_message(chat_id, role, content):
    conn = get_db()
    conn.execute(
        "INSERT INTO messages(chat_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (chat_id, role, content, time.time()),
    )
    conn.commit()
    conn.close()


def get_messages(chat_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE chat_id = ? ORDER BY id",
        [chat_id],
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_chats(mode):
    conn = get_db()
    rows = conn.execute(
        "SELECT id, title, created_at FROM chats WHERE mode = ? ORDER BY id DESC",
        [mode],
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_note(title, body_encrypted):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO notes(title, body, created_at) VALUES (?, ?, ?)",
        (title, body_encrypted, time.time()),
    )
    note_id = cur.lastrowid
    conn.commit()
    conn.close()
    return note_id


def list_notes():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, title, created_at FROM notes ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_note_body(note_id):
    conn = get_db()
    row = conn.execute(
        "SELECT body FROM notes WHERE id = ?", [note_id]
    ).fetchone()
    conn.close()
    return row["body"] if row else None


def delete_note(note_id):
    conn = get_db()
    conn.execute("DELETE FROM notes WHERE id = ?", [note_id])
    conn.commit()
    conn.close()
