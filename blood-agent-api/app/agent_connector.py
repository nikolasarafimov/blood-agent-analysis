import uuid
import tempfile
import os
import sys
from pathlib import Path

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'blood-agent'))

from src.agent import create_blood_agent
from src.models import AgentDependencies
from src.model_config import get_model_config
from storage.minio_storage import MinioConfig, client


async def run_agent_with_file(prompt: str, file_bytes: bytes, filename: str):
    suffix = Path(filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        tmp_file.write(file_bytes)
        tmp_filepath = tmp_file.name

    try:
        cfg = MinioConfig()
        mc = client(cfg)

        deps = AgentDependencies(
            minio_client=mc,
            minio_config=cfg,
            filepath=tmp_filepath,
            language="mkd+eng"
        )

        model_config = get_model_config()
        blood_agent = create_blood_agent(model_config)

        result = await blood_agent.run(prompt, deps=deps)

        return {
            "doc_id": deps.doc_id,
            "text_key": getattr(deps, 'text_key', None),
            "anonymized_key": getattr(deps, 'anonymized_key', None),
            "json_key": getattr(deps, 'json_key', None),
            "loinc_key": getattr(deps, 'loinc_key', None),
            "output": str(result.data) if hasattr(result, 'data') else str(result.output)
        }
    finally:
        if os.path.exists(tmp_filepath):
            os.remove(tmp_filepath)