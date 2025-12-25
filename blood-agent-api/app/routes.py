from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import List

from .agent_connector import run_agent_with_files
from .models import AgentResponse, AgentResponseList
from storage.minio_storage import MinioConfig, client, get_json
from db.sqlite_db import get_record

router = APIRouter()

@router.post(
    "/run-agent",
    response_model=AgentResponseList,
    summary="Process blood test results",
    description="Upload PDFs or images and process them using an AI agent"
)
async def run_agent_endpoint(
    files: List[UploadFile] = File(..., description="PDF or image"),
    prompt: str = Form("Process these documents", description="Prompt for the agent"),
):
    file_payloads = []
    for f in files:
        content = await f.read()
        file_payloads.append((content, f.filename))

    result = await run_agent_with_files(prompt, file_payloads)
    return result

@router.get(
    "/results/{doc_id}",
    summary="Get structured lab JSON by doc_id"
)
async def get_results(doc_id: str):
    cfg = MinioConfig()
    mc = client(cfg)

    rec = get_record(doc_id)
    if not rec:
        raise HTTPException(status_code=404, detail="record not found")

    json_key = rec.get("lab_items") or rec.get("json_pointer") or rec.get("json_key")
    if not json_key:
        raise HTTPException(status_code=404, detail="no JSON pointer for this doc_id")

    try:
        data = get_json(mc, cfg.silver_bucket, json_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"error reading JSON: {e}")

    return data