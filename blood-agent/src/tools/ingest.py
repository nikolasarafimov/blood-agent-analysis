from __future__ import annotations

import logging
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
from src.model_config import ModelConfig, get_model_config
from src.models import RawText
from src.tools.extract_text import (
    ExtractTextInput,
    extract_text,
    extract_text_with_llm,
)
from src.tools.preview import create_preview_and_store
from storage.minio_storage import (
    MinioConfig,
    ensure_bucket,
    put_original,
    put_text,
)

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".bmp",
    ".webp",
}


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _positive_env_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _matches_file_signature(suffix: str, header: bytes) -> bool:
    if suffix == ".pdf":
        return header.startswith(b"%PDF-")
    if suffix == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if suffix in {".jpg", ".jpeg"}:
        return header.startswith(b"\xff\xd8\xff")
    if suffix in {".tif", ".tiff"}:
        return header.startswith((b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"))
    if suffix == ".bmp":
        return header.startswith(b"BM")
    if suffix == ".webp":
        return len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP"
    return False


def _validate_input_file(filepath: str) -> Path:
    if not isinstance(filepath, str) or not filepath.strip():
        raise ValueError("filepath is required")

    path = Path(filepath).expanduser().resolve()

    if not path.is_file():
        raise FileNotFoundError(f"Input file not found: {filepath}")

    suffix = path.suffix.lower()
    if suffix not in _SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {suffix or 'unknown'}")

    size = path.stat().st_size
    if size == 0:
        raise ValueError("Input document is empty")

    max_bytes = _positive_env_int("MAX_UPLOAD_MB", 20) * 1024 * 1024
    if size > max_bytes:
        raise ValueError("Input document exceeds maximum allowed size")

    with path.open("rb") as stream:
        header = stream.read(16)

    if not _matches_file_signature(suffix, header):
        raise ValueError("File content does not match its extension")

    return path


def _require_llm_ocr_permission() -> None:
    if not _env_flag("ENABLE_LLM_OCR", default=False):
        raise RuntimeError("LLM OCR was requested but ENABLE_LLM_OCR is disabled")

    if not _env_flag("ALLOW_UNREDACTED_LLM_OCR", default=False):
        raise RuntimeError(
            "LLM OCR requires explicit permission to transmit unredacted document images"
        )


def ingest_extract_text(
    filepath: str,
    language: Optional[str] = None,
    use_llm: bool = False,
    model_config: Optional[ModelConfig] = None,
) -> RawText:
    path = _validate_input_file(filepath)
    inp = ExtractTextInput(filepath=str(path), language=language)

    if not use_llm:
        return extract_text(inp)

    _require_llm_ocr_permission()

    if model_config is None:
        model_config = get_model_config()

    return extract_text_with_llm(inp, model_config=model_config)


def ingest_then_extract(
    mc: Minio,
    cfg: MinioConfig,
    filepath: str,
    language: Optional[str] = None,
    model_config: Optional[ModelConfig] = None,
    use_llm_ocr: Optional[bool] = None,
) -> str:
    path = _validate_input_file(filepath)

    if use_llm_ocr is None:
        use_llm_ocr = _env_flag("ENABLE_LLM_OCR", default=False)

    if use_llm_ocr:
        _require_llm_ocr_permission()
        if model_config is None:
            model_config = get_model_config()

    ensure_bucket(mc, cfg.bronze_bucket)

    doc_id = str(uuid.uuid4())
    insert_record(
        doc_id,
        bucket=cfg.bronze_bucket,
        key=None,
        status="created",
        filename=path.name,
    )

    try:
        original_key, _content_type, _etag, _size = put_original(
            mc,
            cfg.bronze_bucket,
            str(path),
            doc_id,
        )

        set_original_pointer(doc_id, cfg.bronze_bucket, original_key)
        set_status(doc_id, "original_stored")

        try:
            preview_key = create_preview_and_store(mc, cfg, doc_id, str(path))
            if preview_key:
                set_preview_image_key(
                    doc_id,
                    preview_key,
                    bucket=cfg.bronze_bucket,
                )
        except Exception:
            logger.exception("Preview generation failed for document %s", doc_id)

        raw = ingest_extract_text(
            filepath=str(path),
            language=language,
            use_llm=use_llm_ocr,
            model_config=model_config,
        )

        if not raw.text.strip():
            raise ValueError("Text extraction produced empty output")

        text_key, _text_etag = put_text(
            mc,
            cfg.bronze_bucket,
            doc_id,
            raw.text,
        )

        set_text_pointer(doc_id, key=text_key, bucket=cfg.bronze_bucket)
        set_error(doc_id, "")
        set_status(doc_id, "extracted")

        return doc_id

    except Exception as exc:
        logger.exception("Document ingestion failed for document %s", doc_id)
        set_error(doc_id, f"Ingestion failed ({type(exc).__name__})")
        set_status(doc_id, "error")
        raise