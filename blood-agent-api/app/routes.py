from fastapi import APIRouter, UploadFile, File, Form
from .agent_connector import run_agent_with_file
from .models import AgentResponse

router = APIRouter()

@router.post("/run-agent", response_model=AgentResponse)
async def run_agent_endpoint(
    file: UploadFile = File(...),
    prompt: str = Form("Process this document")
):
    file_bytes = await file.read()

    result = run_agent_with_file(prompt, file_bytes, file.filename)
    return result
