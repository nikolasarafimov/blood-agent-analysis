from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from starlette.concurrency import run_in_threadpool

from db.sqlite_db import get_record, set_error, set_filename, set_status
from src.agent import create_blood_agent
from src.model_config import get_model_config
from src.models import AgentDependencies
from storage.minio_storage import MinioConfig, client

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"
}

_REQUIRED_POINTERS = (
    "original_key",
    "text_key",
    "anonymized_key",
    "json_key",
    "editable_json_key",
)


def _positive_env_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _safe_filename(filename: str) -> str:
    if not isinstance(filename, str):
        raise ValueError("Invalid uploaded filename")

    name = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()

    if (
        not name
        or name in {".", ".."}
        or any(ord(char) < 32 or ord(char) == 127 for char in name)
        or len(name.encode("utf-8")) > 255
    ):
        raise ValueError("Invalid uploaded filename")

    if Path(name).suffix.lower() not in _SUPPORTED_EXTENSIONS:
        raise ValueError("Unsupported uploaded file type")

    return name


def _matches_file_signature(suffix: str, content: bytes) -> bool:
    if suffix == ".pdf":
        return content.startswith(b"%PDF-")
    if suffix == ".png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if suffix in {".jpg", ".jpeg"}:
        return content.startswith(b"\xff\xd8\xff")
    if suffix in {".tif", ".tiff"}:
        return content.startswith(
            (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+")
        )
    if suffix == ".bmp":
        return content.startswith(b"BM")
    if suffix == ".webp":
        return (
            len(content) >= 12
            and content[:4] == b"RIFF"
            and content[8:12] == b"WEBP"
        )
    return False


def _validate_upload(file_bytes: bytes, filename: str) -> str:
    safe_name = _safe_filename(filename)

    if not isinstance(file_bytes, bytes):
        raise TypeError("Uploaded file contents must be bytes")

    if not file_bytes:
        raise ValueError("Uploaded file is empty")

    max_bytes = _positive_env_int("MAX_UPLOAD_MB", 20) * 1024 * 1024

    if len(file_bytes) > max_bytes:
        raise ValueError("Uploaded file exceeds the maximum allowed size")

    if not _matches_file_signature(
        Path(safe_name).suffix.lower(),
        file_bytes[:16],
    ):
        raise ValueError(
            "Uploaded file content does not match its extension"
        )

    return safe_name


def _verify_pipeline_result(doc_id: str) -> Dict[str, Any]:
    record = get_record(doc_id)

    if not record:
        raise RuntimeError(
            "Document metadata was not found after processing"
        )

    if record.get("status") != "loinc_enriched":
        raise RuntimeError(
            "Document pipeline did not reach its final stage"
        )

    if not all(record.get(pointer) for pointer in _REQUIRED_POINTERS):
        raise RuntimeError(
            "Document pipeline is missing required storage artifacts"
        )

    return record


def _mark_incomplete_document(doc_id: str, error: Exception) -> None:
    record = get_record(doc_id)

    if not record or record.get("status") == "error":
        return

    if (
        record.get("status") == "loinc_enriched"
        and all(record.get(pointer) for pointer in _REQUIRED_POINTERS)
    ):
        return

    set_error(
        doc_id,
        f"API processing failed ({type(error).__name__})",
    )
    set_status(doc_id, "error")


def _run_pipeline_sync(
    prompt: str,
    file_bytes: bytes,
    filename: str,
    language: str = "mkd+eng",
) -> Dict[str, Any]:
    safe_filename = _validate_upload(file_bytes, filename)
    extension = Path(safe_filename).suffix.lower()

    dependencies: Optional[AgentDependencies] = None

    try:
        with tempfile.TemporaryDirectory(
            prefix="blood-agent-upload-"
        ) as temp_dir:
            temp_path = Path(temp_dir) / f"upload{extension}"
            temp_path.write_bytes(file_bytes)

            minio_config = MinioConfig()
            minio_client = client(minio_config)
            model_config = get_model_config()

            blood_agent = create_blood_agent(
                model_config=model_config
            )

            dependencies = AgentDependencies(
                minio_client=minio_client,
                minio_config=minio_config,
                filepath=str(temp_path),
                language=language,
            )

            blood_agent.run_sync(
                "Process this laboratory document through the complete pipeline. "
                "Use the required tools in order, and confirm only after completion.",
                deps=dependencies,
            )

            doc_id = dependencies.doc_id

            if not doc_id:
                raise RuntimeError(
                    "Agent finished without assigning a document ID"
                )

            set_filename(doc_id, safe_filename)

            record = _verify_pipeline_result(doc_id)

            return {
                "success": True,
                "filename": safe_filename,
                "doc_id": doc_id,
                "status": record["status"],
                "preview_image_key": (
                    record.get("preview_key")
                    or record.get("preview_image_key")
                ),
                "original_key": record.get("original_key"),
                "text_key": record.get("text_key"),
                "anonymized_key": (
                    record.get("editable_anonymized_key")
                    or record.get("anonymized_key")
                ),
                "json_key": record.get("json_key"),
                "loinc_key": record.get("editable_json_key"),
                "output": f"Document {doc_id} processed successfully.",
            }

    except Exception as exc:
        doc_id = getattr(dependencies, "doc_id", None)

        if doc_id:
            try:
                set_filename(doc_id, safe_filename)
            except Exception:
                logger.warning(
                    "Could not restore the original document filename"
                )

            try:
                _mark_incomplete_document(doc_id, exc)
            except Exception:
                logger.warning(
                    "Could not update the failed document status"
                )

        logger.error(
            "Document processing failed (%s)",
            type(exc).__name__,
        )

        raise


async def run_pipeline_with_file(
    prompt: str,
    file_bytes: bytes,
    filename: str,
    language: str = "mkd+eng",
) -> Dict[str, Any]:
    return await run_in_threadpool(
        _run_pipeline_sync,
        prompt,
        file_bytes,
        filename,
        language,
    )


async def run_pipeline_with_files(
    prompt: str,
    files: List[Tuple[bytes, str]],
    language: str = "mkd+eng",
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []

    for file_bytes, filename in files:
        try:
            result = await run_pipeline_with_file(
                prompt=prompt,
                file_bytes=file_bytes,
                filename=filename,
                language=language,
            )

            results.append(result)

        except Exception:
            results.append({
                "success": False,
                "filename": (
                    filename if isinstance(filename, str) else None
                ),
                "status": "error",
                "error": "Document processing failed",
            })

    return results