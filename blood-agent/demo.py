from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from db.sqlite_db import get_record, set_error, set_status
from src.agent import create_blood_agent
from src.model_config import ModelConfig, get_model_config
from src.models import AgentDependencies
from storage.minio_storage import MinioConfig, client


_REQUIRED_POINTERS = (
    "original_key",
    "text_key",
    "anonymized_key",
    "json_key",
    "editable_json_key",
)


def _resolve_model_config(
    provider: Optional[str],
    model_name: Optional[str],
    base_url: Optional[str],
) -> ModelConfig:
    if any(value is not None for value in (provider, model_name, base_url)):
        return ModelConfig(
            provider=provider,
            model_name=model_name,
            base_url=base_url,
        )

    return get_model_config()


def _verify_completed_document(doc_id: str) -> None:
    record = get_record(doc_id)

    if not record:
        raise RuntimeError("Document metadata was not found after processing")

    if record.get("status") != "loinc_enriched":
        raise RuntimeError("Document processing did not reach the final stage")

    if not all(record.get(pointer) for pointer in _REQUIRED_POINTERS):
        raise RuntimeError("Document processing is missing required storage artifacts")


def _mark_incomplete_document(doc_id: Optional[str], error: Exception) -> None:
    if not doc_id:
        return

    try:
        record = get_record(doc_id)

        if not record or record.get("status") == "error":
            return

        if (
            record.get("status") == "loinc_enriched"
            and all(record.get(pointer) for pointer in _REQUIRED_POINTERS)
        ):
            return

        set_error(doc_id, f"Demo processing failed ({type(error).__name__})")
        set_status(doc_id, "error")
    except Exception:
        print(
            "Warning: document processing status could not be updated",
            file=sys.stderr,
        )


def run_demo(
    filepath: str,
    language: str = "mkd+eng",
    model_provider: Optional[str] = None,
    model_name: Optional[str] = None,
    model_base_url: Optional[str] = None,
) -> str:
    load_dotenv(override=False)

    if not isinstance(filepath, str) or not filepath.strip():
        raise ValueError("Input file path is required")

    path = Path(filepath).expanduser().resolve()

    if not path.is_file():
        raise FileNotFoundError("Input document was not found")

    model_config = _resolve_model_config(
        provider=model_provider,
        model_name=model_name,
        base_url=model_base_url,
    )

    minio_config = MinioConfig()
    minio_client = client(minio_config)
    agent = create_blood_agent(model_config=model_config)

    dependencies = AgentDependencies(
        minio_client=minio_client,
        minio_config=minio_config,
        filepath=str(path),
        language=language,
    )

    try:
        agent.run_sync(
            "Process this laboratory document through the complete pipeline.",
            deps=dependencies,
        )

        doc_id = dependencies.doc_id
        if not doc_id:
            raise RuntimeError("Agent finished without assigning a document ID")

        _verify_completed_document(doc_id)

    except Exception as exc:
        _mark_incomplete_document(dependencies.doc_id, exc)
        raise

    print(f"Model: {model_config.provider}/{model_config.model_name}")
    print(f"Document type: {path.suffix.lower()}")
    print(f"Document ID: {doc_id}")
    print("Status: loinc_enriched")
    print("Document processing completed successfully")

    return doc_id


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the laboratory document processing pipeline on one PDF or image"
    )

    parser.add_argument(
        "filepath",
        type=str,
        help="Path to a laboratory PDF or image",
    )

    parser.add_argument(
        "--language",
        type=str,
        default="mkd+eng",
        help="Tesseract OCR language or language combination",
    )

    parser.add_argument(
        "--model-provider",
        type=str,
        choices=["openai", "anthropic", "ollama"],
        default=None,
    )

    parser.add_argument("--model-name", type=str, default=None)
    parser.add_argument("--model-base-url", type=str, default=None)

    args = parser.parse_args()

    try:
        run_demo(
            filepath=args.filepath,
            language=args.language,
            model_provider=args.model_provider,
            model_name=args.model_name,
            model_base_url=args.model_base_url,
        )
    except Exception as exc:
        print(
            f"Demo processing failed ({type(exc).__name__})",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())