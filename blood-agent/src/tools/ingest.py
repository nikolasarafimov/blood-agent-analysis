from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Optional

from minio import Minio

from db.sqlite_db import (
    insert_record,
    set_error,
    set_original_pointer,
    set_preview_image_key,
    set_status,
    set_text_pointer,
)
from src.model_config import get_model_config
from src.models import RawText
from storage.minio_storage import MinioConfig, ensure_bucket, put_original, put_text
from src.tools.extract_text import ExtractTextInput, extract_text, extract_text_with_llm
from src.tools.preview import create_preview_and_store


def ingest_extract_text(
    filepath: str,
    language: Optional[str] = None,
    use_llm: bool = False,
    model_config=None,
) -> RawText:
    """
    Just extract text (no MinIO, no DB).
    """
    inp = ExtractTextInput(filepath=filepath, language=language)
    if use_llm:
        if model_config is None:
            model_config = get_model_config()
        return extract_text_with_llm(inp, model_config=model_config)
    return extract_text(inp)


def ingest_then_extract(
    mc: Minio,
    cfg: MinioConfig,
    filepath: str,
    language: Optional[str] = None,
    model_config=None,
    use_llm_ocr: Optional[bool] = None,
) -> str:
    """
    Full pipeline step #1:
    - generate doc_id
    - store original in bronze
    - create & store preview in bronze (best-effort)
    - extract text (fast OCR; optional LLM OCR)
    - store extracted .txt in bronze
    - update sqlite pointers/status

    Returns: doc_id
    """
    if model_config is None:
        model_config = get_model_config()

    if not filepath:
        raise ValueError("filepath is required")
    fp = Path(filepath)
    if not fp.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    # Decide whether to use LLM OCR (optional env toggle)
    if use_llm_ocr is None:
        use_llm_ocr = os.getenv("USE_LLM_OCR", "false").lower() == "true"

    ensure_bucket(mc, cfg.bronze_bucket)
    ensure_bucket(mc, cfg.silver_bucket)

    doc_id = str(uuid.uuid4())
    filename = fp.name

    # Create DB record early
    insert_record(doc_id, bucket=cfg.bronze_bucket, key=None, status="created", filename=filename)

    try:
        # 1) store original
        orig_key, _ctype, _etag, _size = put_original(mc, cfg.bronze_bucket, str(fp), doc_id)
        set_original_pointer(doc_id, cfg.bronze_bucket, orig_key)
        set_status(doc_id, "original_stored")

        # 2) preview (best-effort)
        try:
            preview_key = create_preview_and_store(mc, cfg, doc_id, str(fp))
            if preview_key:
                set_preview_image_key(doc_id, preview_key, bucket=cfg.bronze_bucket)
        except Exception:
            # preview is not critical
            pass

        # 3) extract text
        raw = ingest_extract_text(
            filepath=str(fp),
            language=language,
            use_llm=bool(use_llm_ocr),
            model_config=model_config,
        )

        # 4) store extracted text in bronze
        text_key, _etag2 = put_text(mc, cfg.bronze_bucket, doc_id, raw.text)
        set_text_pointer(doc_id, key=text_key, bucket=cfg.bronze_bucket)
        set_status(doc_id, "extracted")

        return doc_id

    except Exception as e:
        set_error(doc_id, f"ingest_then_extract failed: {e}")
        set_status(doc_id, "error")
        raise
