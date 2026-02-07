from __future__ import annotations

import io
import json
import os
from typing import Any, List, Literal, Optional
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Request
from fastapi.responses import StreamingResponse
from minio.error import S3Error
from pydantic import BaseModel

from .agent_connector import run_pipeline_with_files
from db.sqlite_db import (
    delete_doc,
    get_record,
    get_saved_rows,
    set_editable_json_key,
    set_editable_text_key,
    upsert_lab_row,
)
from storage.minio_storage import (
    MinioConfig,
    client,
    delete_prefix,
    get_json,
    get_text_object,
    put_json,
)

router = APIRouter()


def _file_url(request: Request, bucket: str, key: Optional[str]) -> Optional[str]:
    if not key:
        return None
    base = str(request.base_url).rstrip("/")
    safe_key = quote(key, safe="/")
    return f"{base}/files/{bucket}/{safe_key}"


def _guess_content_type(key: str) -> str:
    key_lower = (key or "").lower()
    if key_lower.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if key_lower.endswith(".png"):
        return "image/png"
    if key_lower.endswith(".pdf"):
        return "application/pdf"
    if key_lower.endswith(".txt"):
        return "text/plain; charset=utf-8"
    if key_lower.endswith(".json"):
        return "application/json; charset=utf-8"
    return "application/octet-stream"


def _require_record(doc_id: str) -> dict:
    rec = get_record(doc_id)
    if not rec:
        raise HTTPException(status_code=404, detail="record not found")
    return rec


def _max_upload_bytes() -> int:
    raw = os.getenv("MAX_UPLOAD_MB", "20")
    try:
        max_mb = int(raw)
    except Exception:
        max_mb = 20
    if max_mb <= 0:
        max_mb = 20
    return max_mb * 1024 * 1024


class SaveTextRequest(BaseModel):
    type: Literal["extracted", "anonymized", "json"]
    content: str = ""


class SaveRowRequest(BaseModel):
    parameter: Optional[str] = None
    value: Optional[Any] = None
    unit: Optional[str] = None
    reference_min: Optional[float] = None
    reference_max: Optional[float] = None
    loinc_code: Optional[str] = None
    loinc_display: Optional[str] = None


class RunAgentResult(BaseModel):
    doc_id: Optional[str] = None
    status: str = "error"
    filename: Optional[str] = None
    preview_url: Optional[str] = None
    original_url: Optional[str] = None
    output: Optional[str] = None


@router.post("/run-agent", summary="Upload and process documents", response_model=List[RunAgentResult])
async def run_agent_endpoint(
    request: Request,
    files: List[UploadFile] = File(...),
    prompt: str = Form("Process these documents"),
    language: str = Form("mkd+eng"),
):
    max_bytes = _max_upload_bytes()

    file_payloads: List[tuple[bytes, str]] = []
    for f in files:
        name = f.filename or "upload.bin"
        content = await f.read()
        if not content:
            raise HTTPException(status_code=400, detail=f"empty file: {name}")
        if len(content) > max_bytes:
            max_mb = int(os.getenv("MAX_UPLOAD_MB", "20") or "20")
            raise HTTPException(status_code=413, detail=f"file too large: {name} (max {max_mb}MB)")
        file_payloads.append((content, name))

    try:
        results = await run_pipeline_with_files(prompt, file_payloads, language=language)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"pipeline failed: {e}")

    cfg = MinioConfig()
    out: List[RunAgentResult] = []

    for r in results:
        doc_id = r.get("doc_id")
        if not doc_id:
            out.append(RunAgentResult(doc_id=None, status="error", output=r.get("output") or "missing doc_id"))
            continue

        rec = get_record(doc_id) or {}
        preview_key = rec.get("preview_image_key")
        original_key = rec.get("key") or rec.get("original_key")

        out.append(
            RunAgentResult(
                doc_id=doc_id,
                status=str(rec.get("status") or "unknown"),
                filename=rec.get("filename"),
                preview_url=_file_url(request, cfg.bronze_bucket, preview_key),
                original_url=_file_url(request, cfg.bronze_bucket, original_key),
                output=r.get("output", "OK"),
            )
        )

    return out


@router.get("/docs/{doc_id}", summary="Get doc metadata")
async def get_doc(request: Request, doc_id: str):
    rec = _require_record(doc_id)
    cfg = MinioConfig()

    preview_key = rec.get("preview_image_key")
    original_key = rec.get("key") or rec.get("original_key")

    return {
        "doc_id": doc_id,
        "status": rec.get("status"),
        "filename": rec.get("filename"),
        "preview_url": _file_url(request, cfg.bronze_bucket, preview_key),
        "original_url": _file_url(request, cfg.bronze_bucket, original_key),
    }


@router.get("/files/{bucket}/{key:path}", summary="Serve file from MinIO")
async def serve_file(bucket: str, key: str):
    cfg = MinioConfig()
    allowed = {cfg.bronze_bucket, cfg.silver_bucket}
    if bucket not in allowed:
        raise HTTPException(status_code=404, detail="bucket not found")

    mc = client(cfg)

    try:
        obj = mc.get_object(bucket, key)
    except S3Error:
        raise HTTPException(status_code=404, detail="file not found")

    def iterator():
        try:
            for chunk in obj.stream(1024 * 64):
                yield chunk
        finally:
            try:
                obj.close()
            finally:
                obj.release_conn()

    return StreamingResponse(iterator(), media_type=_guess_content_type(key))


@router.get("/docs/{doc_id}/text", summary="Get editable text/json")
async def get_doc_text(
    doc_id: str,
    type: Literal["extracted", "anonymized", "json"] = "json",
):
    cfg = MinioConfig()
    mc = client(cfg)
    rec = _require_record(doc_id)

    extracted_key = rec.get("text_key")
    anonymized_key = rec.get("editable_text_key") or rec.get("anonymized_txt") or rec.get("anonymized_key")
    json_key = rec.get("editable_json_key") or rec.get("json_key") or rec.get("loinc_key")

    if type == "extracted":
        if not extracted_key:
            raise HTTPException(status_code=404, detail="no extracted text")
        return {"type": type, "content": get_text_object(mc, cfg.bronze_bucket, extracted_key)}

    if type == "anonymized":
        if not anonymized_key:
            raise HTTPException(status_code=404, detail="no anonymized text")
        return {"type": type, "content": get_text_object(mc, cfg.silver_bucket, anonymized_key)}

    if not json_key:
        raise HTTPException(status_code=404, detail="no json available")
    data = get_json(mc, cfg.silver_bucket, json_key)
    return {"type": type, "content": json.dumps(data, indent=2, ensure_ascii=False)}


@router.put("/docs/{doc_id}/text", summary="Save edited text/json")
async def save_doc_text(doc_id: str, body: SaveTextRequest):
    cfg = MinioConfig()
    mc = client(cfg)
    _ = _require_record(doc_id)

    if body.type in ("extracted", "anonymized"):
        key = f"documents/{doc_id}/user_{body.type}.txt"
        data = (body.content or "").encode("utf-8")

        mc.put_object(
            cfg.silver_bucket,
            key,
            io.BytesIO(data),
            length=len(data),
            content_type="text/plain; charset=utf-8",
        )

        set_editable_text_key(doc_id, editable_text_key=key)
        return {"ok": True, "key": key}

    try:
        obj = json.loads(body.content or "")
        if not isinstance(obj, dict):
            raise ValueError("top-level JSON must be an object")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid json: {e}")

    key = f"documents/{doc_id}/user_json.json"
    data = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")

    mc.put_object(
        cfg.silver_bucket,
        key,
        io.BytesIO(data),
        length=len(data),
        content_type="application/json; charset=utf-8",
    )

    set_editable_json_key(doc_id, editable_json_key=key)
    return {"ok": True, "key": key}


@router.post("/docs/{doc_id}/regenerate-json", summary="Regenerate JSON from current editable text")
async def regenerate_json(doc_id: str):
    cfg = MinioConfig()
    mc = client(cfg)
    rec = _require_record(doc_id)

    text_key = rec.get("editable_text_key") or rec.get("anonymized_txt") or rec.get("anonymized_key")
    if text_key:
        text = get_text_object(mc, cfg.silver_bucket, text_key)
    else:
        extracted = rec.get("text_key")
        if not extracted:
            raise HTTPException(status_code=404, detail="no text available to regenerate from")
        text = get_text_object(mc, cfg.bronze_bucket, extracted)

    from src.model_config import get_model_config
    from src.tools.txt_to_json import text_to_json_with_llm

    model_config = get_model_config()
    try:
        result_json = text_to_json_with_llm(text, model_config=model_config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"regeneration failed: {e}")

    new_key = put_json(mc, cfg.silver_bucket, doc_id, result_json, suffix="regenerated")
    set_editable_json_key(doc_id, editable_json_key=new_key)

    return {"ok": True, "json_key": new_key, "json": result_json}


@router.get("/results/{doc_id}", summary="Get structured lab JSON by doc_id")
async def get_results(doc_id: str):
    cfg = MinioConfig()
    mc = client(cfg)
    rec = _require_record(doc_id)

    json_key = rec.get("editable_json_key") or rec.get("json_key")
    if not json_key:
        raise HTTPException(status_code=404, detail="no JSON pointer for this doc_id")

    try:
        data = get_json(mc, cfg.silver_bucket, json_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"error reading JSON: {e}")

    return data


@router.put("/docs/{doc_id}/rows/{row_index}", summary="Save one row to DB")
async def save_row(doc_id: str, row_index: int, row: SaveRowRequest):
    _ = _require_record(doc_id)
    if row_index < 0:
        raise HTTPException(status_code=400, detail="row_index must be >= 0")
    upsert_lab_row(doc_id, row_index, row.model_dump())
    return {"ok": True}


@router.get("/docs/{doc_id}/rows", summary="Get saved rows from DB")
async def list_rows(doc_id: str):
    _ = _require_record(doc_id)
    return {"rows": get_saved_rows(doc_id)}


@router.delete("/docs/{doc_id}", summary="Delete doc (MinIO + DB)")
async def delete_document(doc_id: str):
    cfg = MinioConfig()
    mc = client(cfg)
    _ = _require_record(doc_id)

    prefix = f"documents/{doc_id}/"

    try:
        delete_prefix(mc, cfg.bronze_bucket, prefix)
    except Exception:
        pass
    try:
        delete_prefix(mc, cfg.silver_bucket, prefix)
    except Exception:
        pass

    delete_doc(doc_id)
    return {"ok": True}