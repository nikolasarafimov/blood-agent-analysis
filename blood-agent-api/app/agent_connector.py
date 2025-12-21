import os
import sys
import uuid

# Ensure the main `blood-agent` package folder is on sys.path so imports like
# `from src.agent ...` work when the API runs from a different working dir.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BP = os.path.join(ROOT, "blood-agent")
if BP not in sys.path:
    sys.path.insert(0, BP)

from src.agent import blood_agent
from src.models import AgentDependencies
from storage.minio_storage import MinioConfig, client as minio_client_factory
import tempfile
from pathlib import Path

async def run_agent_with_file(prompt: str, file_bytes: bytes, filename: str, uploaded_by: str | None = None):

    doc_id = str(uuid.uuid4())

    # Write uploaded bytes to a temporary file so the ingest pipeline can access it by path
    tmp_dir = tempfile.gettempdir()
    tmp_path = Path(tmp_dir) / f"{doc_id}_{filename}"
    with open(tmp_path, "wb") as f:
        f.write(file_bytes)

    # Initialize MinIO client/config from env or defaults
    cfg = MinioConfig()
    mc = minio_client_factory(cfg)

    deps = AgentDependencies(
        minio_client=mc,
        minio_config=cfg,
        filepath=str(tmp_path),
        doc_id=doc_id,
        language="mkd+eng",
        uploaded_by=uploaded_by,
    )

    # Use the agent's async `run` method to avoid `event loop already running` errors
    result = await blood_agent.run(prompt, deps=deps)
    return {
        "doc_id": doc_id,
        "text_key": getattr(deps, "text_key", None),
        "anonymized_key": getattr(deps, "anonymized_key", None),
        "json_key": getattr(deps, "json_key", None),
        "loinc_key": getattr(deps, "loinc_key", None),
        "output": result.output
    }
