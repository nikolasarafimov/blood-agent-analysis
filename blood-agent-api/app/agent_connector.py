import tempfile
import os
import sys
from pathlib import Path

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "blood-agent"))

from src.agent import create_blood_agent
from src.models import AgentDependencies
from src.model_config import get_model_config
from storage.minio_storage import MinioConfig, client
from src.tools.ingest import ingest_then_extract


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
            language="mkd+eng",
        )

        doc_id = ingest_then_extract(
            mc=mc,
            cfg=cfg,
            filepath=tmp_filepath,
            language=deps.language,
        )
        deps.doc_id = doc_id

        model_config = get_model_config()
        blood_agent = create_blood_agent(model_config)

        try:
            result = await blood_agent.run(prompt, deps=deps)
            output = str(getattr(result, "output", ""))
        except Exception as e:
            output = f"[agent error] {e}"

        return {
            "doc_id": deps.doc_id,
            "text_key": getattr(deps, "text_key", None),
            "anonymized_key": getattr(deps, "anonymized_key", None),
            "json_key": getattr(deps, "json_key", None),
            "loinc_key": getattr(deps, "loinc_key", None),
            "output": output,
        }

    finally:
        if os.path.exists(tmp_filepath):
            os.remove(tmp_filepath)


async def run_agent_with_files(prompt: str, files: list[tuple[bytes, str]]):
    """
    files: list of (file_bytes, filename)
    """
    results = []
    for file_bytes, filename in files:
        res = await run_agent_with_file(prompt, file_bytes, filename)
        results.append(res)

    return results
