from __future__ import annotations

import io
import json
import logging
import math
import os
import re
from pathlib import Path, PureWindowsPath
from typing import Any, Literal, Optional
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from minio.error import S3Error
from pydantic import BaseModel, ValidationError, field_validator

from .agent_connector import run_pipeline_with_files
from db.sqlite_db import (
    delete_doc,
    get_record,
    get_saved_rows,
    set_editable_anonymized_key,
    set_editable_extracted_key,
    set_editable_json_key,
    set_json,
    upsert_lab_row,
)
from src.models import LabItem, LaboratoryResults
from src.tools.loinc_validation import validate_and_enrich_loinc_codes
from src.tools.txt_to_json import parse_to_json
from storage.minio_storage import (
    MinioConfig,
    client,
    delete_prefix,
    ensure_bucket,
    get_json,
    get_text_object,
    put_json,
)

logger = logging.getLogger(__name__)
router = APIRouter()

_SUPPORTED_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"
}
_ALLOWED_TEST_FIELDS = set(LabItem.model_fields)
_LANGUAGE_PATTERN = re.compile(r"[A-Za-z0-9_]{2,30}(?:\+[A-Za-z0-9_]{2,30})*")
_PRIVATE_HEADERS = {
    "Cache-Control": "private, no-store",
    "Pragma": "no-cache",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


class SaveTextRequest(BaseModel):
    type: Literal["extracted", "anonymized", "json"]
    content: str = ""


class SaveRowRequest(BaseModel):
    parameter: Optional[str] = None
    value: float | str | None = None
    abnormal_flag: Optional[Literal["low", "high"]] = None
    unit: Optional[str] = None
    reference_min: Optional[float] = None
    reference_max: Optional[float] = None
    loinc_code: Optional[str] = None
    loinc_display: Optional[str] = None

    @field_validator("value", "reference_min", "reference_max", mode="before")
    @classmethod
    def reject_invalid_number(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("Boolean values are not valid laboratory measurements")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Non-finite measurements are not allowed")
        return value


class RunAgentResult(BaseModel):
    success: bool = False
    doc_id: Optional[str] = None
    status: str = "error"
    filename: Optional[str] = None
    preview_url: Optional[str] = None
    original_url: Optional[str] = None
    output: Optional[str] = None
    error: Optional[str] = None


def _set_private_headers(response: Response) -> None:
    for name, value in _PRIVATE_HEADERS.items():
        response.headers[name] = value


def _file_url(request: Request, bucket: str, key: Optional[str]) -> Optional[str]:
    if not key:
        return None
    base = str(request.base_url).rstrip("/")
    return f"{base}/files/{quote(bucket, safe='')}/{quote(key, safe='/')}"


def _file_pointers(record: dict, cfg: MinioConfig) -> dict[str, tuple[str, Optional[str]]]:
    return {
        "original": (
            record.get("original_bucket") or cfg.bronze_bucket,
            record.get("original_key") or record.get("key"),
        ),
        "preview": (
            record.get("preview_bucket") or cfg.bronze_bucket,
            record.get("preview_key") or record.get("preview_image_key"),
        ),
    }


def _document_urls(request: Request, record: dict, cfg: MinioConfig) -> dict[str, Optional[str]]:
    pointers = _file_pointers(record, cfg)
    original_bucket, original_key = pointers["original"]
    preview_bucket, preview_key = pointers["preview"]
    return {
        "original_url": _file_url(request, original_bucket, original_key),
        "preview_url": _file_url(request, preview_bucket, preview_key),
    }


def _guess_content_type(key: str) -> str:
    suffix = Path(key).suffix.lower()
    return {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }.get(suffix, "application/octet-stream")


def _require_record(doc_id: str) -> dict:
    record = get_record(doc_id)
    if not record:
        raise HTTPException(status_code=404, detail="Document not found")
    return record


def _positive_env_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (ValueError, TypeError):
        return default
    return value if value > 0 else default


def _sanitize_filename(filename: Optional[str]) -> str:
    name = Path(PureWindowsPath(filename or "").name).name.strip()
    if not name or name in {".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if any(ord(char) < 32 or ord(char) == 127 for char in name):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if len(name.encode("utf-8")) > 255:
        raise HTTPException(status_code=400, detail="Filename is too long")
    return name


def _matches_file_signature(suffix: str, content: bytes) -> bool:
    if suffix == ".pdf":
        return content.startswith(b"%PDF-")
    if suffix == ".png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if suffix in {".jpg", ".jpeg"}:
        return content.startswith(b"\xff\xd8\xff")
    if suffix in {".tif", ".tiff"}:
        return content.startswith((b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"))
    if suffix == ".bmp":
        return content.startswith(b"BM")
    if suffix == ".webp":
        return (
            len(content) >= 12
            and content[:4] == b"RIFF"
            and content[8:12] == b"WEBP"
        )
    return False


def _storage_error_to_http(exc: Exception, not_found_detail: str) -> HTTPException:
    if isinstance(exc, S3Error) and exc.code in {"NoSuchKey", "NoSuchBucket", "NoSuchObject"}:
        return HTTPException(status_code=404, detail=not_found_detail)
    logger.error("Storage operation failed (%s)", type(exc).__name__)
    return HTTPException(status_code=502, detail="Storage operation failed")


async def _read_upload_limited(upload: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while chunk := await upload.read(1024 * 1024):
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(status_code=413, detail="Uploaded file exceeds maximum size")
        chunks.append(chunk)
    return b"".join(chunks)


def _put_editable_text(mc: Any, bucket: str, key: str, content: str) -> None:
    ensure_bucket(mc, bucket)
    payload = content.encode("utf-8")
    mc.put_object(
        bucket_name=bucket,
        object_name=key,
        data=io.BytesIO(payload),
        length=len(payload),
        content_type="text/plain; charset=utf-8",
    )


def _reject_json_constant(value: str) -> None:
    raise ValueError("Non-finite JSON numbers are not allowed")


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON keys are not allowed")
        result[key] = value
    return result


def _finite_json_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("Non-finite JSON numbers are not allowed")
    return parsed


def _ensure_finite_numbers(test: dict, index: int) -> None:
    for field in ("value", "reference_min", "reference_max"):
        value = test.get(field)
        if isinstance(value, bool):
            raise HTTPException(status_code=400, detail=f"Invalid {field} at row {index}")
        if isinstance(value, (int, float)) and not math.isfinite(value):
            raise HTTPException(status_code=400, detail=f"Non-finite {field} at row {index}")


def _validate_laboratory_json(data: Any) -> dict:
    if not isinstance(data, dict) or set(data) != {"tests"}:
        raise HTTPException(status_code=400, detail="JSON must contain only the 'tests' top-level key")

    tests = data.get("tests")
    if not isinstance(tests, list) or not tests:
        raise HTTPException(status_code=400, detail="JSON must contain a non-empty tests array")

    for index, test in enumerate(tests):
        if not isinstance(test, dict) or set(test) - _ALLOWED_TEST_FIELDS:
            raise HTTPException(status_code=400, detail=f"Invalid fields at row {index}")
        for field in ("value", "reference_min", "reference_max"):
            _ensure_finite_numbers({field: test.get(field)}, index)

    try:
        normalized = LaboratoryResults.model_validate(data).model_dump(mode="json")
    except (ValidationError, ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=400,
            detail="JSON does not match the laboratory results schema",
        ) from exc

    for index, test in enumerate(normalized["tests"]):
        if test.get("value") is None:
            raise HTTPException(status_code=400, detail=f"Missing value at row {index}")
        _ensure_finite_numbers(test, index)
        low, high = test.get("reference_min"), test.get("reference_max")
        if low is not None and high is not None and low > high:
            raise HTTPException(status_code=400, detail=f"Invalid reference interval at row {index}")

    return normalized


def _current_json_pointer(record: dict, cfg: MinioConfig) -> tuple[str, str]:
    key = record.get("editable_json_key") or record.get("json_key")
    if not key:
        raise HTTPException(status_code=404, detail="No JSON available for this document")
    return record.get("json_bucket") or cfg.silver_bucket, key


def _load_current_json(mc: Any, record: dict, cfg: MinioConfig) -> dict:
    bucket, key = _current_json_pointer(record, cfg)
    try:
        data = get_json(mc, bucket, key)
    except Exception as exc:
        raise _storage_error_to_http(exc, "JSON not found") from exc
    if not isinstance(data, dict) or not isinstance(data.get("tests"), list):
        raise HTTPException(status_code=502, detail="Stored laboratory JSON has an invalid structure")
    return data


@router.post(
    "/run-agent",
    summary="Upload and process documents",
    response_model=list[RunAgentResult],
)
async def run_agent_endpoint(
    request: Request,
    response: Response,
    files: list[UploadFile] = File(...),
    prompt: str = Form("Process these documents"),
    language: str = Form("mkd+eng"),
):
    _set_private_headers(response)
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")
    max_files = _positive_env_int("MAX_UPLOAD_FILES", 5)
    if len(files) > max_files:
        raise HTTPException(status_code=400, detail=f"Maximum {max_files} files per request")
    if len(prompt) > _positive_env_int("MAX_PROMPT_CHARS", 10000):
        raise HTTPException(status_code=413, detail="Prompt exceeds maximum length")
    if len(language) > 100 or not _LANGUAGE_PATTERN.fullmatch(language.strip()):
        raise HTTPException(status_code=400, detail="Invalid OCR language selection")

    max_bytes = _positive_env_int("MAX_UPLOAD_MB", 20) * 1024 * 1024
    file_payloads: list[tuple[bytes, str]] = []

    for upload in files:
        try:
            filename = _sanitize_filename(upload.filename)
            extension = Path(filename).suffix.lower()
            if extension not in _SUPPORTED_EXTENSIONS:
                raise HTTPException(status_code=415, detail="Unsupported file type")
            contents = await _read_upload_limited(upload, max_bytes)
            if not contents:
                raise HTTPException(status_code=400, detail="Uploaded file is empty")
            if not _matches_file_signature(extension, contents[:16]):
                raise HTTPException(
                    status_code=415,
                    detail="File content does not match its extension",
                )
            file_payloads.append((contents, filename))
        finally:
            await upload.close()

    try:
        results = await run_pipeline_with_files(
            prompt=prompt,
            files=file_payloads,
            language=language.strip(),
        )
    except Exception as exc:
        logger.error("Pipeline execution failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=500, detail="Pipeline execution failed") from exc

    cfg = MinioConfig()
    output: list[RunAgentResult] = []
    for result in results:
        doc_id = result.get("doc_id")
        if not result.get("success") or not doc_id:
            output.append(RunAgentResult(
                success=False,
                doc_id=doc_id,
                filename=result.get("filename"),
                error="Document processing failed",
            ))
            continue

        record = get_record(doc_id)
        if not record:
            output.append(RunAgentResult(
                success=False,
                doc_id=doc_id,
                filename=result.get("filename"),
                error="Document metadata is unavailable",
            ))
            continue

        output.append(RunAgentResult(
            success=True,
            doc_id=doc_id,
            status=str(record.get("status") or "unknown"),
            filename=record.get("filename") or result.get("filename"),
            output=result.get("output") or "OK",
            **_document_urls(request, record, cfg),
        ))

    return output


@router.get("/docs/{doc_id}", summary="Get document metadata")
def get_doc(request: Request, response: Response, doc_id: str):
    _set_private_headers(response)
    record = _require_record(doc_id)
    return {
        "doc_id": doc_id,
        "status": record.get("status"),
        "filename": record.get("filename"),
        **_document_urls(request, record, MinioConfig()),
    }


@router.get("/files/{bucket}/{key:path}", summary="Serve document preview or original file")
def serve_file(bucket: str, key: str):
    cfg = MinioConfig()
    parts = key.split("/", 2)
    if len(parts) != 3 or parts[0] != "documents" or not parts[1]:
        raise HTTPException(status_code=404, detail="File not found")

    record = _require_record(parts[1])
    if (bucket, key) not in set(_file_pointers(record, cfg).values()):
        raise HTTPException(status_code=404, detail="File not found")

    mc = client(cfg)
    try:
        obj = mc.get_object(bucket_name=bucket, object_name=key)
    except Exception as exc:
        raise _storage_error_to_http(exc, "File not found") from exc

    def iterator():
        try:
            yield from obj.stream(64 * 1024)
        finally:
            try:
                obj.close()
            finally:
                obj.release_conn()

    return StreamingResponse(
        iterator(),
        media_type=_guess_content_type(key),
        headers=_PRIVATE_HEADERS.copy(),
    )


@router.get("/docs/{doc_id}/text", summary="Get editable text or JSON")
def get_doc_text(
    response: Response,
    doc_id: str,
    type: Literal["extracted", "anonymized", "json"] = "json",
):
    _set_private_headers(response)
    cfg = MinioConfig()
    record = _require_record(doc_id)
    mc = client(cfg)

    if type == "json":
        data = _load_current_json(mc, record, cfg)
        return {"type": type, "content": json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)}

    if type == "extracted":
        key = record.get("editable_extracted_key") or record.get("text_key")
        bucket = record.get("text_bucket") or cfg.bronze_bucket
    else:
        key = record.get("editable_anonymized_key") or record.get("anonymized_key") or record.get("anonymized_txt")
        bucket = record.get("anonymized_bucket") or cfg.silver_bucket

    if not key:
        raise HTTPException(status_code=404, detail=f"No {type} text available")

    try:
        content = get_text_object(mc, bucket, key)
    except Exception as exc:
        raise _storage_error_to_http(exc, f"{type.capitalize()} text not found") from exc

    return {"type": type, "content": content}


@router.put("/docs/{doc_id}/text", summary="Save edited text or JSON")
def save_doc_text(response: Response, doc_id: str, body: SaveTextRequest):
    _set_private_headers(response)
    cfg = MinioConfig()
    record = _require_record(doc_id)

    max_bytes = _positive_env_int("MAX_EDIT_TEXT_MB", 8) * 1024 * 1024
    if len(body.content.encode("utf-8")) > max_bytes:
        raise HTTPException(status_code=413, detail="Edited content exceeds maximum size")

    mc = client(cfg)
    if body.type == "json":
        try:
            parsed = json.loads(
                body.content,
                parse_constant=_reject_json_constant,
                parse_float=_finite_json_float,
                object_pairs_hook=_reject_duplicate_json_keys,
            )
        except (json.JSONDecodeError, ValueError, OverflowError) as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON") from exc

        validated = _validate_laboratory_json(parsed)
        target_bucket = record.get("json_bucket") or cfg.silver_bucket
        try:
            key = put_json(mc, target_bucket, doc_id, validated, suffix="user")
        except Exception as exc:
            raise _storage_error_to_http(exc, "Unable to save JSON") from exc

        set_json(doc_id, validated, bucket=target_bucket, key=key)
        set_editable_json_key(doc_id, editable_json_key=key)
        return {"ok": True, "key": key}

    if body.type == "extracted":
        bucket = record.get("text_bucket") or cfg.bronze_bucket
        key = f"documents/{doc_id}/user_extracted.txt"
        setter = set_editable_extracted_key
    else:
        bucket = record.get("anonymized_bucket") or cfg.silver_bucket
        key = f"documents/{doc_id}/user_anonymized.txt"
        setter = set_editable_anonymized_key

    try:
        _put_editable_text(mc, bucket, key, body.content)
    except Exception as exc:
        raise _storage_error_to_http(exc, f"Unable to save {body.type} text") from exc

    setter(doc_id, key)
    return {"ok": True, "key": key}


@router.post("/docs/{doc_id}/regenerate-json", summary="Regenerate JSON from current anonymized text")
def regenerate_json(response: Response, doc_id: str):
    _set_private_headers(response)
    record = _require_record(doc_id)
    if not (
        record.get("editable_anonymized_key")
        or record.get("anonymized_key")
        or record.get("anonymized_txt")
    ):
        raise HTTPException(status_code=409, detail="Anonymized text is unavailable")

    cfg = MinioConfig()
    mc = client(cfg)
    try:
        parse_to_json(mc, cfg, doc_id)
        key = validate_and_enrich_loinc_codes(mc, cfg, doc_id)
        updated_record = _require_record(doc_id)
        bucket = updated_record.get("json_bucket") or cfg.silver_bucket
        result_json = get_json(mc, bucket, key)
    except Exception as exc:
        logger.error("JSON regeneration failed for document %s (%s)", doc_id, type(exc).__name__)
        raise HTTPException(status_code=500, detail="JSON regeneration failed") from exc

    return {"ok": True, "json_key": key, "json": result_json}


@router.get("/results/{doc_id}", summary="Get structured laboratory JSON")
def get_results(response: Response, doc_id: str):
    _set_private_headers(response)
    cfg = MinioConfig()
    record = _require_record(doc_id)
    return _load_current_json(client(cfg), record, cfg)


@router.put("/docs/{doc_id}/rows/{row_index}", summary="Save one edited laboratory row")
def save_row(response: Response, doc_id: str, row_index: int, row: SaveRowRequest):
    _set_private_headers(response)
    record = _require_record(doc_id)
    if row_index < 0:
        raise HTTPException(status_code=400, detail="row_index must be nonnegative")

    cfg = MinioConfig()
    data = _load_current_json(client(cfg), record, cfg)
    tests = data["tests"]
    if row_index >= len(tests):
        raise HTTPException(status_code=404, detail="Laboratory row not found")

    base = tests[row_index]
    if not isinstance(base, dict):
        raise HTTPException(status_code=502, detail="Stored laboratory row has an invalid structure")

    merged = base.copy()
    for saved in get_saved_rows(doc_id):
        candidate_index = saved.get("row_index", saved.get("row_id"))
        try:
            candidate_index = int(candidate_index)
        except (ValueError, TypeError):
            continue
        if candidate_index == row_index:
            merged.update({k: v for k, v in saved.items() if k in _ALLOWED_TEST_FIELDS})
            break

    merged.update(row.model_dump(exclude_unset=True))
    try:
        validated = LabItem.model_validate(merged).model_dump(mode="json")
    except (ValidationError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid laboratory row") from exc

    if validated.get("value") is None:
        raise HTTPException(status_code=400, detail="Laboratory result value cannot be empty")

    _ensure_finite_numbers(validated, row_index)
    upsert_lab_row(doc_id, row_index, validated)
    return {"ok": True, "row_index": row_index}


@router.get("/docs/{doc_id}/rows", summary="Get saved laboratory rows")
def list_rows(response: Response, doc_id: str):
    _set_private_headers(response)
    _require_record(doc_id)
    return {"rows": get_saved_rows(doc_id)}


@router.delete("/docs/{doc_id}", summary="Delete document and stored artifacts")
def delete_document(response: Response, doc_id: str):
    _set_private_headers(response)
    record = _require_record(doc_id)
    cfg = MinioConfig()
    mc = client(cfg)

    buckets = {cfg.bronze_bucket, cfg.silver_bucket}
    for field in (
        "original_bucket",
        "preview_bucket",
        "text_bucket",
        "anonymized_bucket",
        "json_bucket",
    ):
        bucket = record.get(field)
        if bucket:
            buckets.add(bucket)

    failed = 0
    for bucket in buckets:
        try:
            delete_prefix(mc, bucket, f"documents/{doc_id}/")
        except Exception as exc:
            logger.error("Document storage cleanup failed (%s)", type(exc).__name__)
            failed += 1

    if failed:
        raise HTTPException(
            status_code=502,
            detail="Storage cleanup failed. Document metadata was preserved for retry.",
        )

    try:
        delete_doc(doc_id)
    except Exception as exc:
        logger.error("Document metadata deletion failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=500, detail="Document metadata deletion failed") from exc

    return {"ok": True}