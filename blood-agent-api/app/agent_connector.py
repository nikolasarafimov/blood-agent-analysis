import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

from starlette.concurrency import run_in_threadpool

from storage.minio_storage import MinioConfig, client
from src.model_config import get_model_config
from src.tools.ingest import ingest_then_extract
from src.tools.anonymize import anonymize_and_store_by_doc_id
from src.tools.txt_to_json import parse_to_json
from src.tools.loinc_validation import validate_and_enrich_loinc_codes
from db.sqlite_db import get_record, set_filename


def _run_pipeline_sync(prompt: str, file_bytes: bytes, filename: str, language: str = "mkd+eng") -> Dict[str, Any]:
    suffix = Path(filename).suffix or ".bin"
    tmp_filepath = None

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        tmp_file.write(file_bytes)
        tmp_filepath = tmp_file.name

    try:
        cfg = MinioConfig()
        mc = client(cfg)
        model_config = get_model_config()

        doc_id = ingest_then_extract(
            mc=mc,
            cfg=cfg,
            filepath=tmp_filepath,
            language=language,
            model_config=model_config,
        )

        try:
            set_filename(doc_id, filename)
        except Exception:
            pass

        anonymize_and_store_by_doc_id(mc, cfg, doc_id, model_config=model_config)

        parse_to_json(mc, cfg, doc_id, model_config=model_config)

        validate_and_enrich_loinc_codes(mc, cfg, doc_id, model_config=model_config)

        rec = get_record(doc_id) or {}
        return {
            "doc_id": doc_id,
            "preview_image_key": rec.get("preview_image_key"),
            "original_key": rec.get("key") or rec.get("original_key"),
            "output": "OK",
        }

    finally:
        if tmp_filepath and os.path.exists(tmp_filepath):
            os.remove(tmp_filepath)


async def run_pipeline_with_file(prompt: str, file_bytes: bytes, filename: str) -> Dict[str, Any]:
    return await run_in_threadpool(_run_pipeline_sync, prompt, file_bytes, filename)


async def run_pipeline_with_files(prompt: str, files: List[Tuple[bytes, str]]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for file_bytes, filename in files:
        res = await run_pipeline_with_file(prompt, file_bytes, filename)
        results.append(res)
    return results