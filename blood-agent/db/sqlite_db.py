from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

_DB_LOCK = threading.Lock()


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _db_path() -> str:
    path = (
        os.getenv("SQLITE_DB_PATH")
        or os.getenv("DB_PATH")
        or "bronze.sqlite3"
    )

    Path(path).parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    return path


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(
        _db_path(),
        check_same_thread=False,
        timeout=30.0,
    )

    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000;")

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
                    editable_extracted_key TEXT,
                    editable_anonymized_key TEXT,
                    filename TEXT
                );
                """
            )

            cur.execute("PRAGMA table_info(documents);")

            existing_cols = {
                row["name"]
                for row in cur.fetchall()
            }

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
                "editable_extracted_key": "TEXT",
                "editable_anonymized_key": "TEXT",
                "filename": "TEXT",
            }

            for column, ddl in desired_cols.items():
                if column not in existing_cols:
                    cur.execute(
                        f"ALTER TABLE documents ADD COLUMN {column} {ddl};"
                    )

            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_documents_updated_at
                ON documents(updated_at);
                """
            )

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

            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_lab_rows_doc_id
                ON lab_rows(doc_id);
                """
            )

            conn.commit()

        finally:
            conn.close()


def _normalize_json(value: Any) -> str:
    if value is None:
        return "null"

    if isinstance(value, str):
        stripped = value.strip()

        if stripped:
            try:
                parsed = json.loads(stripped)

                json.dumps(
                    parsed,
                    ensure_ascii=False,
                    allow_nan=False,
                )

                return stripped

            except (
                json.JSONDecodeError,
                ValueError,
                TypeError,
                OverflowError,
            ):
                pass

        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
        )

    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    )


def _stable_row_id(
    doc_id: str,
    row_obj: Any,
) -> str:
    blob = _normalize_json(row_obj).encode("utf-8")
    digest = hashlib.sha1(blob).hexdigest()[:16]

    return f"{doc_id[:8]}_{digest}"


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
    editable_extracted_key: Optional[str] = None,
    editable_anonymized_key: Optional[str] = None,
    filename: Optional[str] = None,
    invalidate_saved_rows: bool = False,
) -> None:
    init_db()

    now = _now_iso()

    fields: Dict[str, Any] = {
        "doc_id": doc_id,
        "updated_at": now,
    }

    candidates = {
        "status": status,
        "error": error,
        "original_bucket": original_bucket,
        "original_key": original_key,
        "text_bucket": text_bucket,
        "text_key": text_key,
        "anonymized_bucket": anonymized_bucket,
        "anonymized_key": anonymized_key,
        "preview_bucket": preview_bucket,
        "preview_key": preview_key,
        "json_bucket": json_bucket,
        "json_key": json_key,
        "json_text": json_text,
        "editable_json_key": editable_json_key,
        "editable_text_key": editable_text_key,
        "editable_extracted_key": editable_extracted_key,
        "editable_anonymized_key": editable_anonymized_key,
        "filename": filename,
    }

    fields.update(
        {
            key: value
            for key, value in candidates.items()
            if value is not None
        }
    )

    columns = list(fields)
    insert_columns = columns + ["created_at"]

    insert_columns_sql = ", ".join(insert_columns)
    placeholders_sql = ", ".join(
        "?" for _ in insert_columns
    )

    update_sql = ", ".join(
        f"{column}=excluded.{column}"
        for column in columns
        if column != "doc_id"
    )

    values = [
        fields[column]
        for column in columns
    ] + [now]

    with _DB_LOCK:
        conn = _connect()

        try:
            conn.execute(
                f"""
                INSERT INTO documents ({insert_columns_sql})
                VALUES ({placeholders_sql})
                ON CONFLICT(doc_id) DO UPDATE SET
                    {update_sql};
                """,
                values,
            )

            if invalidate_saved_rows:
                conn.execute(
                    "DELETE FROM lab_rows WHERE doc_id = ?",
                    (doc_id,),
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
    _upsert_base(
        doc_id,
        status=status,
        original_bucket=bucket,
        original_key=key,
        filename=filename,
    )


def get_record(
    doc_id: str,
) -> Optional[Dict[str, Any]]:
    init_db()

    with _DB_LOCK:
        conn = _connect()

        try:
            row = conn.execute(
                "SELECT * FROM documents WHERE doc_id = ?",
                (doc_id,),
            ).fetchone()

            if row is None:
                return None

            record = dict(row)

            record.setdefault(
                "key",
                record.get("original_key"),
            )

            record.setdefault(
                "preview_image_key",
                record.get("preview_key"),
            )

            record.setdefault(
                "anonymized_txt",
                record.get("anonymized_key"),
            )

            return record

        finally:
            conn.close()


def delete_doc(doc_id: str) -> None:
    init_db()

    with _DB_LOCK:
        conn = _connect()

        try:
            conn.execute(
                "DELETE FROM lab_rows WHERE doc_id = ?",
                (doc_id,),
            )

            conn.execute(
                "DELETE FROM documents WHERE doc_id = ?",
                (doc_id,),
            )

            conn.commit()

        finally:
            conn.close()


def set_status(
    doc_id: str,
    status: str,
) -> None:
    _upsert_base(
        doc_id,
        status=status,
    )


def set_error(
    doc_id: str,
    error: str,
) -> None:
    _upsert_base(
        doc_id,
        error=error,
    )


def set_bucket(
    doc_id: str,
    bucket: str,
) -> None:
    _upsert_base(
        doc_id,
        original_bucket=bucket,
    )


def set_original_pointer(
    doc_id: str,
    bucket: str,
    key: str,
) -> None:
    _upsert_base(
        doc_id,
        original_bucket=bucket,
        original_key=key,
    )


def set_text_pointer(
    doc_id: str,
    key: str,
    bucket: Optional[str] = None,
) -> None:
    _upsert_base(
        doc_id,
        text_bucket=bucket,
        text_key=key,
    )


def set_preview_image_key(
    doc_id: str,
    key: str,
    bucket: Optional[str] = None,
) -> None:
    _upsert_base(
        doc_id,
        preview_bucket=bucket,
        preview_key=key,
    )


def set_anonymized_text_pointer(
    doc_id: str,
    key: str,
    bucket: Optional[str] = None,
) -> None:
    _upsert_base(
        doc_id,
        anonymized_bucket=bucket,
        anonymized_key=key,
    )


def set_anonymized_txt(
    doc_id: str,
    key: str,
) -> None:
    set_anonymized_text_pointer(
        doc_id,
        key,
    )


def set_json(
    doc_id: str,
    json_value: Any,
    bucket: Optional[str] = None,
    key: Optional[str] = None,
) -> None:
    _upsert_base(
        doc_id,
        json_bucket=bucket,
        json_key=key,
        json_text=_normalize_json(json_value),
        invalidate_saved_rows=True,
    )


def set_editable_json_key(
    doc_id: str,
    editable_json_key: str,
) -> None:
    _upsert_base(
        doc_id,
        editable_json_key=editable_json_key,
        invalidate_saved_rows=True,
    )


def set_editable_extracted_key(
    doc_id: str,
    editable_extracted_key: str,
) -> None:
    _upsert_base(
        doc_id,
        editable_extracted_key=editable_extracted_key,
    )


def set_editable_anonymized_key(
    doc_id: str,
    editable_anonymized_key: str,
) -> None:
    _upsert_base(
        doc_id,
        editable_anonymized_key=editable_anonymized_key,
        editable_text_key=editable_anonymized_key,
    )


def set_editable_text_key(
    doc_id: str,
    editable_text_key: str,
) -> None:
    set_editable_anonymized_key(
        doc_id,
        editable_text_key,
    )


def set_filename(
    doc_id: str,
    filename: str,
) -> None:
    _upsert_base(
        doc_id,
        filename=filename,
    )


def _upsert_lab_row_by_id(
    doc_id: str,
    row_obj: Union[Dict[str, Any], List[Any], str],
    row_id: Optional[str] = None,
) -> str:
    init_db()

    inferred_row_id: Optional[str] = None

    if isinstance(row_obj, dict):
        if row_obj.get("row_id") is not None:
            inferred_row_id = str(
                row_obj["row_id"]
            )

    resolved_row_id = (
        row_id
        or inferred_row_id
        or _stable_row_id(doc_id, row_obj)
    )

    row_json = _normalize_json(row_obj)
    now = _now_iso()

    with _DB_LOCK:
        conn = _connect()

        try:
            conn.execute(
                """
                INSERT INTO lab_rows (
                    doc_id,
                    row_id,
                    row_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(doc_id, row_id) DO UPDATE SET
                    row_json=excluded.row_json,
                    updated_at=excluded.updated_at;
                """,
                (
                    doc_id,
                    resolved_row_id,
                    row_json,
                    now,
                    now,
                ),
            )

            conn.commit()

        finally:
            conn.close()

    return resolved_row_id


def upsert_lab_row(
    doc_id: str,
    a: Union[int, Dict[str, Any], List[Any], str],
    b: Optional[Union[Dict[str, Any], List[Any], str]] = None,
) -> str:
    if b is None:
        return _upsert_lab_row_by_id(
            doc_id,
            a,
        )

    return _upsert_lab_row_by_id(
        doc_id,
        b,
        row_id=str(a),
    )


def get_saved_rows(
    doc_id: str,
) -> List[Dict[str, Any]]:
    init_db()

    with _DB_LOCK:
        conn = _connect()

        try:
            entries = conn.execute(
                """
                SELECT
                    row_id,
                    row_json,
                    created_at,
                    updated_at
                FROM lab_rows
                WHERE doc_id = ?
                ORDER BY id ASC
                """,
                (doc_id,),
            ).fetchall()

            rows: List[Dict[str, Any]] = []

            for entry in entries:
                row_id = str(
                    entry["row_id"]
                )

                try:
                    parsed = json.loads(
                        entry["row_json"]
                    )

                except (
                    json.JSONDecodeError,
                    TypeError,
                ):
                    parsed = {
                        "raw": entry["row_json"],
                    }

                if isinstance(parsed, dict):
                    output = parsed.copy()

                    if output.get("row_id") is None:
                        output["row_id"] = row_id

                else:
                    output = {
                        "row_id": row_id,
                        "value": parsed,
                    }

                if row_id.isdigit():
                    output["row_index"] = int(
                        row_id
                    )

                output["_created_at"] = entry[
                    "created_at"
                ]

                output["_updated_at"] = entry[
                    "updated_at"
                ]

                rows.append(output)

            return rows

        finally:
            conn.close()


def set_text_key(
    doc_id: str,
    key: str,
) -> None:
    set_text_pointer(
        doc_id,
        key,
    )


def set_extracted_txt(
    doc_id: str,
    key: str,
) -> None:
    set_text_pointer(
        doc_id,
        key,
    )


def set_extracted_text_pointer(
    doc_id: str,
    key: str,
) -> None:
    set_text_pointer(
        doc_id,
        key,
    )


def set_preview_key(
    doc_id: str,
    key: str,
) -> None:
    set_preview_image_key(
        doc_id,
        key,
    )


def set_anonymized_key(
    doc_id: str,
    key: str,
) -> None:
    set_anonymized_text_pointer(
        doc_id,
        key,
    )


def set_json_key(
    doc_id: str,
    key: str,
) -> None:
    _upsert_base(
        doc_id,
        json_key=key,
        invalidate_saved_rows=True,
    )


def set_json_pointer(
    doc_id: str,
    key: str,
    bucket: Optional[str] = None,
) -> None:
    _upsert_base(
        doc_id,
        json_bucket=bucket,
        json_key=key,
        invalidate_saved_rows=True,
    )


def set_bronze_bucket(
    doc_id: str,
    bucket: str,
) -> None:
    set_bucket(
        doc_id,
        bucket,
    )


def set_silver_bucket(
    doc_id: str,
    bucket: str,
) -> None:
    _upsert_base(
        doc_id,
        anonymized_bucket=bucket,
        json_bucket=bucket,
    )


def get_pointers(
    doc_id: str,
) -> Optional[Dict[str, Tuple[Optional[str], Optional[str]]]]:
    record = get_record(doc_id)

    if record is None:
        return None

    editable_anonymized_key = (
        record.get("editable_anonymized_key")
        or record.get("editable_text_key")
    )

    return {
        "original": (
            record.get("original_bucket"),
            record.get("original_key"),
        ),
        "text": (
            record.get("text_bucket"),
            record.get("text_key"),
        ),
        "anonymized": (
            record.get("anonymized_bucket"),
            record.get("anonymized_key"),
        ),
        "preview": (
            record.get("preview_bucket"),
            record.get("preview_key"),
        ),
        "json": (
            record.get("json_bucket"),
            record.get("json_key"),
        ),
        "editable_extracted": (
            record.get("text_bucket"),
            record.get("editable_extracted_key"),
        ),
        "editable_anonymized": (
            record.get("anonymized_bucket"),
            editable_anonymized_key,
        ),
        "editable_text": (
            record.get("anonymized_bucket"),
            editable_anonymized_key,
        ),
        "editable_json": (
            record.get("json_bucket"),
            record.get("editable_json_key"),
        ),
    }