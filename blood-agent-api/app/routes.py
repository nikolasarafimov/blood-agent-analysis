from fastapi import APIRouter, UploadFile, File, Form
from .agent_connector import run_agent_with_file
from .models import AgentResponse

router = APIRouter()


@router.post(
    "/run-agent",
    response_model=AgentResponse,
    summary="Process blood test results",
    description="Upload a PDF or an image and process it using an AI agent"
)
async def run_agent_endpoint(
        file: UploadFile = File(..., description="PDF or image"),
        prompt: str = Form("Process this document", description="Prompt for the agent")
):

    file_bytes = await file.read()
    result = await run_agent_with_file(prompt, file_bytes, file.filename)
    return result