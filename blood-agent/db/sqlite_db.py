from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

_DB_LOCK = threading.Lock()


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _db_path() -> str:
    p = (
        os.getenv("SQLITE_DB_PATH")
        or os.getenv("DB_PATH")
        or "bronze.sqlite3"
    )
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    return p


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _DB_LOCK:
        conn = _connect()
        try:
            cur = conn.cursor()

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id TEXT PRIMARY KEY,
                    status TEXT DEFAULT 'created',
                    error TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    original_bucket TEXT,
                    original_key TEXT,
                    text_bucket TEXT,
                    text_key TEXT,
                    anonymized_bucket TEXT,
                    anonymized_key TEXT,
                    preview_bucket TEXT,
                    preview_key TEXT,
                    json_bucket TEXT,
                    json_key TEXT,
                    json_text TEXT,
                    editable_json_key TEXT,
                    editable_text_key TEXT,
                    filename TEXT
                );
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_documents_updated_at ON documents(updated_at);")

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS lab_rows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id TEXT NOT NULL,
                    row_id TEXT NOT NULL,
                    row_json TEXT NOT NULL,
                    created_at TEXT,
                    updated_at TEXT,
                    UNIQUE(doc_id, row_id)
                );
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_lab_rows_doc_id ON lab_rows(doc_id);")

            cur.execute("PRAGMA table_info(documents);")
            existing_cols = {row["name"] for row in cur.fetchall()}
            desired_cols = {
                "status": "TEXT DEFAULT 'created'",
                "error": "TEXT",
                "created_at": "TEXT",
                "updated_at": "TEXT",
                "original_bucket": "TEXT",
                "original_key": "TEXT",
                "text_bucket": "TEXT",
                "text_key": "TEXT",
                "anonymized_bucket": "TEXT",
                "anonymized_key": "TEXT",
                "preview_bucket": "TEXT",
                "preview_key": "TEXT",
                "json_bucket": "TEXT",
                "json_key": "TEXT",
                "json_text": "TEXT",
                "editable_json_key": "TEXT",
                "editable_text_key": "TEXT",
                "filename": "TEXT",
            }
            for col, ddl in desired_cols.items():
                if col not in existing_cols:
                    cur.execute(f"ALTER TABLE documents ADD COLUMN {col} {ddl};")

            conn.commit()
        finally:
            conn.close()


def _normalize_json(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, str):
        s = value.strip()
        if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
            return value
        return json.dumps(value, ensure_ascii=False)
    return json.dumps(value, ensure_ascii=False, indent=2)


def _stable_row_id(doc_id: str, row_obj: Any) -> str:
    blob = _normalize_json(row_obj).encode("utf-8")
    h = hashlib.sha1(blob).hexdigest()[:16]
    return f"{doc_id[:8]}_{h}"


def _upsert_base(
    doc_id: str,
    *,
    status: Optional[str] = None,
    error: Optional[str] = None,
    original_bucket: Optional[str] = None,
    original_key: Optional[str] = None,
    text_bucket: Optional[str] = None,
    text_key: Optional[str] = None,
    anonymized_bucket: Optional[str] = None,
    anonymized_key: Optional[str] = None,
    preview_bucket: Optional[str] = None,
    preview_key: Optional[str] = None,
    json_bucket: Optional[str] = None,
    json_key: Optional[str] = None,
    json_text: Optional[str] = None,
    editable_json_key: Optional[str] = None,
    editable_text_key: Optional[str] = None,
    filename: Optional[str] = None,
) -> None:
    init_db()
    now = _now_iso()

    fields: Dict[str, Any] = {"doc_id": doc_id, "updated_at": now}

    if status is not None:
        fields["status"] = status
    if error is not None:
        fields["error"] = error

    if original_bucket is not None:
        fields["original_bucket"] = original_bucket
    if original_key is not None:
        fields["original_key"] = original_key

    if text_bucket is not None:
        fields["text_bucket"] = text_bucket
    if text_key is not None:
        fields["text_key"] = text_key

    if anonymized_bucket is not None:
        fields["anonymized_bucket"] = anonymized_bucket
    if anonymized_key is not None:
        fields["anonymized_key"] = anonymized_key

    if preview_bucket is not None:
        fields["preview_bucket"] = preview_bucket
    if preview_key is not None:
        fields["preview_key"] = preview_key

    if json_bucket is not None:
        fields["json_bucket"] = json_bucket
    if json_key is not None:
        fields["json_key"] = json_key
    if json_text is not None:
        fields["json_text"] = json_text

    if editable_json_key is not None:
        fields["editable_json_key"] = editable_json_key
    if editable_text_key is not None:
        fields["editable_text_key"] = editable_text_key

    if filename is not None:
        fields["filename"] = filename

    cols = list(fields.keys())
    insert_cols_sql = ", ".join(cols + ["created_at"])
    placeholders_sql = ", ".join(["?"] * (len(cols) + 1))
    update_cols = [c for c in cols if c != "doc_id"]
    update_sql = ", ".join([f"{c}=excluded.{c}" for c in update_cols])

    values = [fields[c] for c in cols] + [now]

    with _DB_LOCK:
        conn = _connect()
        try:
            conn.execute(
                f"""
                INSERT INTO documents ({insert_cols_sql})
                VALUES ({placeholders_sql})
                ON CONFLICT(doc_id) DO UPDATE SET
                    {update_sql}
                ;
                """,
                values,
            )
            conn.commit()
        finally:
            conn.close()


def insert_record(
    doc_id: str,
    bucket: Optional[str] = None,
    key: Optional[str] = None,
    status: str = "created",
    filename: Optional[str] = None,
    **_kwargs: Any,
) -> None:
    _upsert_base(doc_id, status=status, original_bucket=bucket, original_key=key, filename=filename)


def get_record(doc_id: str) -> Optional[Dict[str, Any]]:
    init_db()
    with _DB_LOCK:
        conn = _connect()
        try:
            cur = conn.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,))
            row = cur.fetchone()
            if not row:
                return None
            d = dict(row)

            if "key" not in d:
                d["key"] = d.get("original_key")
            if "preview_image_key" not in d:
                d["preview_image_key"] = d.get("preview_key")
            if "anonymized_txt" not in d:
                d["anonymized_txt"] = d.get("anonymized_key")

            return d
        finally:
            conn.close()


def delete_doc(doc_id: str) -> None:
    init_db()
    with _DB_LOCK:
        conn = _connect()
        try:
            conn.execute("DELETE FROM lab_rows WHERE doc_id = ?", (doc_id,))
            conn.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
            conn.commit()
        finally:
            conn.close()


def set_status(doc_id: str, status: str) -> None:
    _upsert_base(doc_id, status=status)


def set_error(doc_id: str, error: str) -> None:
    _upsert_base(doc_id, error=error)


def set_bucket(doc_id: str, bucket: str) -> None:
    _upsert_base(doc_id, original_bucket=bucket)


def set_original_pointer(doc_id: str, bucket: str, key: str) -> None:
    _upsert_base(doc_id, original_bucket=bucket, original_key=key)


def set_text_pointer(doc_id: str, key: str, bucket: Optional[str] = None) -> None:
    _upsert_base(doc_id, text_bucket=bucket, text_key=key)


def set_preview_image_key(doc_id: str, key: str, bucket: Optional[str] = None) -> None:
    _upsert_base(doc_id, preview_bucket=bucket, preview_key=key)


def set_anonymized_text_pointer(doc_id: str, key: str, bucket: Optional[str] = None) -> None:
    _upsert_base(doc_id, anonymized_bucket=bucket, anonymized_key=key)


def set_anonymized_txt(doc_id: str, key: str) -> None:
    set_anonymized_text_pointer(doc_id, key)


def set_json(doc_id: str, json_value: Any, bucket: Optional[str] = None, key: Optional[str] = None) -> None:
    json_text = _normalize_json(json_value)
    _upsert_base(doc_id, json_bucket=bucket, json_key=key, json_text=json_text)


def set_editable_json_key(doc_id: str, editable_json_key: str) -> None:
    _upsert_base(doc_id, editable_json_key=editable_json_key)


def set_editable_text_key(doc_id: str, editable_text_key: str) -> None:
    _upsert_base(doc_id, editable_text_key=editable_text_key)


def set_filename(doc_id: str, filename: str) -> None:
    _upsert_base(doc_id, filename=filename)


def _upsert_lab_row_by_id(
    doc_id: str,
    row_obj: Union[Dict[str, Any], List[Any], str],
    row_id: Optional[str] = None,
) -> str:
    init_db()

    inferred: Optional[str] = None
    if isinstance(row_obj, dict):
        for k in ("row_id", "id", "key", "uid"):
            if row_obj.get(k):
                inferred = str(row_obj[k])
                break

    rid = row_id or inferred or _stable_row_id(doc_id, row_obj)
    row_json = _normalize_json(row_obj)
    now = _now_iso()

    with _DB_LOCK:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO lab_rows (doc_id, row_id, row_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(doc_id, row_id) DO UPDATE SET
                    row_json=excluded.row_json,
                    updated_at=excluded.updated_at
                ;
                """,
                (doc_id, rid, row_json, now, now),
            )
            conn.commit()
        finally:
            conn.close()

    return rid


def upsert_lab_row(
    doc_id: str,
    a: Union[int, Dict[str, Any], List[Any], str],
    b: Optional[Union[Dict[str, Any], List[Any], str]] = None,
) -> str:
    if b is None:
        return _upsert_lab_row_by_id(doc_id, a, row_id=None)
    return _upsert_lab_row_by_id(doc_id, b, row_id=str(a))


def get_saved_rows(doc_id: str) -> List[Dict[str, Any]]:
    init_db()
    with _DB_LOCK:
        conn = _connect()
        try:
            cur = conn.execute(
                "SELECT row_id, row_json, created_at, updated_at FROM lab_rows WHERE doc_id=? ORDER BY id ASC",
                (doc_id,),
            )
            out: List[Dict[str, Any]] = []
            for r in cur.fetchall():
                try:
                    parsed = json.loads(r["row_json"])
                except Exception:
                    parsed = {"raw": r["row_json"]}

                if isinstance(parsed, dict):
                    parsed.setdefault("row_id", r["row_id"])
                    parsed.setdefault("_created_at", r["created_at"])
                    parsed.setdefault("_updated_at", r["updated_at"])
                    out.append(parsed)
                else:
                    out.append(
                        {
                            "row_id": r["row_id"],
                            "value": parsed,
                            "_created_at": r["created_at"],
                            "_updated_at": r["updated_at"],
                        }
                    )
            return out
        finally:
            conn.close()


def set_text_key(doc_id: str, key: str) -> None:
    set_text_pointer(doc_id, key)


def set_extracted_txt(doc_id: str, key: str) -> None:
    set_text_pointer(doc_id, key)


def set_extracted_text_pointer(doc_id: str, key: str) -> None:
    set_text_pointer(doc_id, key)


def set_preview_key(doc_id: str, key: str) -> None:
    set_preview_image_key(doc_id, key)


def set_anonymized_key(doc_id: str, key: str) -> None:
    set_anonymized_text_pointer(doc_id, key)


def set_json_key(doc_id: str, key: str) -> None:
    _upsert_base(doc_id, json_key=key)


def set_json_pointer(doc_id: str, key: str, bucket: Optional[str] = None) -> None:
    _upsert_base(doc_id, json_bucket=bucket, json_key=key)


def set_bronze_bucket(doc_id: str, bucket: str) -> None:
    set_bucket(doc_id, bucket)


def set_silver_bucket(doc_id: str, bucket: str) -> None:
    _upsert_base(doc_id, json_bucket=bucket)


def get_pointers(doc_id: str) -> Optional[Dict[str, Tuple[Optional[str], Optional[str]]]]:
    r = get_record(doc_id)
    if not r:
        return None

    editable_bucket = r.get("anonymized_bucket") or r.get("text_bucket")  # editable text usually lives with anonymized
    return {
        "original": (r.get("original_bucket"), r.get("original_key")),
        "text": (r.get("text_bucket"), r.get("text_key")),
        "anonymized": (r.get("anonymized_bucket"), r.get("anonymized_key")),
        "preview": (r.get("preview_bucket"), r.get("preview_key")),
        "json": (r.get("json_bucket"), r.get("json_key")),
        "editable_text": (editable_bucket, r.get("editable_text_key")),
        "editable_json": (r.get("json_bucket"), r.get("editable_json_key")),
    }