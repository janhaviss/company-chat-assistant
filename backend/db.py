import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

DB_PATH = "chatbot.db"


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (lead_id) REFERENCES leads (id)
            )
        """)
        conn.commit()
        existing_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(applications)")
        }
        if "job_title" not in existing_columns:
            conn.execute("ALTER TABLE applications ADD COLUMN job_title TEXT")
            conn.commit()


def save_lead(session_id: str, name: str, email: str, phone: str) -> int:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO leads (session_id, name, email, phone, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                name = excluded.name,
                email = excluded.email,
                phone = excluded.phone
            """,
            (session_id, name, email, phone, datetime.utcnow().isoformat()),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id FROM leads WHERE session_id = ?", (session_id,)
        ).fetchone()
        return row["id"]


def save_application(lead_id: int, file_path: str, original_filename: str, job_title: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO applications (lead_id, file_path, original_filename, job_title, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (lead_id, file_path, original_filename, job_title, datetime.utcnow().isoformat()),
        )
        conn.commit()
        return cur.lastrowid


def get_lead_by_session(session_id: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM leads WHERE session_id = ?", (session_id,)
        ).fetchone()