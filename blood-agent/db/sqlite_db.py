from __future__ import annotations

import datetime as dt
import os
import sqlite3
from typing import Optional, Mapping

DB_PATH = os.getenv("DB_PATH", "./bronze.sqlite3")

def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _ensure_column(c: sqlite3.Connection, table: str, name: str, ddl: str) -> None:
    cols = [r[1] for r in c.execute(f"PRAGMA table_info({table})")]
    if name not in cols:
        c.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def init_db() -> None:
    with _conn() as c:
        # your current schema (unchanged)
        c.execute("""
        CREATE TABLE IF NOT EXISTS record (
            id TEXT PRIMARY KEY,

            bucket TEXT NOT NULL,
            original_key TEXT NOT NULL,
            text_key TEXT,
            filename TEXT,
            language TEXT,
            content_type TEXT,
            size_bytes INTEGER,
            etag_original TEXT,
            etag_text TEXT,
            status TEXT NOT NULL,
            error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)

        # --- minimal additions for anonymization & future steps ---
        _ensure_column(c, "record", "anonymized_txt", "TEXT")  # pointer to anonymized TXT (bronze)
        _ensure_column(c, "record", "lab_items", "TEXT")  # pointer to JSON in silver
        _ensure_column(c, "record", "lab_cache", "TEXT")  # JSON cache of candidates
        _ensure_column(c, "record", "lab_item_class", "TEXT")  # optional class label
        _ensure_column(c, "record", "patient_id", "TEXT")  # manual entry later
        _ensure_column(c, "record", "content_hash", "TEXT")  # for dedup
        _ensure_column(c, "record", "model_provider", "TEXT")  # LLM provider used (openai, anthropic, ollama)
        _ensure_column(c, "record", "model_name", "TEXT")  # LLM model name used (e.g., gpt-4o, claude-3-5-sonnet)
        _ensure_column(c, "record", "uploaded_by", "TEXT")  # username who uploaded the document
        # optional for dedup
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_record_content_hash ON record(content_hash)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_record_anontxt ON record(anonymized_txt)")

# ---------- existing helpers (if you have them, keep) ----------

def insert_record(
    *,
    id: str,
    bucket: str,
    original_key: str,
    filename: str,
    language: Optional[str],
    content_type: Optional[str],
    size_bytes: Optional[int],
    etag_original: Optional[str],
    model_provider: Optional[str] = None,
    model_name: Optional[str] = None,
    uploaded_by: Optional[str] = None,
) -> None:
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with _conn() as c:
        c.execute("""
            INSERT INTO record (
                id, bucket, original_key, text_key, filename, language,
                content_type, size_bytes, etag_original, etag_text,
                status, error, created_at, updated_at, model_provider, model_name, uploaded_by)
            VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, NULL, 'uploaded', NULL, ?, ?, ?, ?, ?)
        """, (id, bucket, original_key, filename, language, content_type, size_bytes,
              etag_original, now, now, model_provider, model_name, uploaded_by))

def set_text_pointer(
    id: str,
    *,
    text_key: str,
    etag_text: Optional[str],
) -> None:
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with _conn() as c:
        c.execute("""
            UPDATE record
               SET text_key = ?, etag_text = ?, status = 'processed', updated_at = ?
             WHERE id = ?
        """, (text_key, etag_text, now, id))

def set_error(id: str, message: str) -> None:
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with _conn() as c:
        c.execute("""
            UPDATE record
               SET status = 'error', error = ?, updated_at = ?
             WHERE id = ?
        """, (message[:500], now, id))

def get_record(id: str) -> Optional[Mapping]:
    with _conn() as c:
        row = c.execute("SELECT * FROM record WHERE id = ?", (id,)).fetchone()
        return dict(row) if row else None


def set_anonymized_txt(id: str, *, anonymized_txt_pointer: str) -> None:
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with _conn() as c:
        c.execute("""
            UPDATE record
               SET anonymized_txt = ?, updated_at = ?
             WHERE id = ?
        """, (anonymized_txt_pointer, now, id))


def set_json(id: str, *, json_pointer: str) -> None:
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with _conn() as c:
        c.execute("""
                  UPDATE record
                  SET lab_items  = ?,
                      updated_at = ?
                  WHERE id = ?
                  """, (json_pointer, now, id))

def set_status(id: str, *, status: str) -> None:
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with _conn() as c:
        c.execute("""
            UPDATE record
               SET status = ?, updated_at = ?
             WHERE id = ?
        """, (status, now, id))


def set_bucket(id: str, *, bucket: str) -> None:
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with _conn() as c:
        c.execute("""
                  UPDATE record
                  SET bucket     = ?,
                      updated_at = ?
                  WHERE id = ?
                  """, (bucket, now, id))


# (optional, if you’ll need them soon)
def set_lab_items_pointer(id: str, *, lab_items_pointer: str) -> None:
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with _conn() as c:
        c.execute("""
            UPDATE record
               SET lab_items = ?, updated_at = ?
             WHERE id = ?
        """, (lab_items_pointer, now, id))

def set_lab_cache(id: str, *, lab_cache_json: str) -> None:
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    with _conn() as c:
        c.execute("""
            UPDATE record
               SET lab_cache = ?, updated_at = ?
             WHERE id = ?
        """, (lab_cache_json, now, id))


