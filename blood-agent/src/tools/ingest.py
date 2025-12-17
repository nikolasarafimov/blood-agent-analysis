from __future__ import annotations

import datetime
import os
from typing import Optional

from minio import Minio

from db.sqlite_db import init_db, insert_record, set_text_pointer, set_error
from src.model_config import get_model_config
from src.tools.extract_text import ExtractTextInput, extract_text_with_llm
from storage.minio_storage import MinioConfig, ensure_bucket, put_original, put_text


def ingest_then_extract(mc: Minio, cfg: MinioConfig, filepath: str, language: Optional[str], model_config=None) -> str:
    """
    Core pipeline logic to save, extract, and update records.
    Returns the doc_id to be used by the caller.

    1) Save original to MinIO (bronze)
    2) Create SQLite record (status=uploaded)
    3) Convert to image if it is PDF
    4) Extract text from image
    5) Save .txt with same doc_id
    6) Update record (status=processed)
    """

    init_db()
    ensure_bucket(mc, cfg.bronze_bucket)

    # Get model config early so we can store it in the record
    if model_config is None:
        model_config = get_model_config()

    doc_id = str(datetime.datetime.now())

    # 1) upload original FIRST
    original_key, ctype, etag, size = put_original(mc, cfg.bronze_bucket, filepath, doc_id)

    # 2) insert metadata row with model information
    insert_record(
        id=doc_id,
        bucket=cfg.bronze_bucket,
        original_key=original_key,
        filename=os.path.basename(filepath),
        language=language,
        content_type=ctype,
        size_bytes=size,
        etag_original=etag,
        model_provider=model_config.provider,
        model_name=model_config.model_name,
    )

    try:
        # 3) extract text

        out = extract_text_with_llm(ExtractTextInput(filepath=filepath, language=language), model_config=model_config)
        text = out.text if hasattr(out, "text") else str(out)

        print(text)

        # 4) upload .txt with SAME doc_id
        text_key, text_etag = put_text(mc, cfg.bronze_bucket, doc_id, text)

        # 5) update row
        set_text_pointer(doc_id, text_key=text_key, etag_text=text_etag)

        return doc_id

    except Exception as e:
        set_error(doc_id, str(e))
        raise
