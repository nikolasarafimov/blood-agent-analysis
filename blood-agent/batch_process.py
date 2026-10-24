from __future__ import annotations

import os
import platform
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional, Union

from dotenv import load_dotenv

load_dotenv()

if platform.system() == "Windows":
    poppler_path = os.getenv("POPPLER_PATH")
    if poppler_path and os.path.isdir(poppler_path):
        os.environ["PATH"] = poppler_path + os.pathsep + os.environ.get("PATH", "")

from db.sqlite_db import get_record, set_error, set_status
from src.agent import create_blood_agent
from src.model_config import ModelConfig, get_model_config
from src.models import AgentDependencies
from storage.minio_storage import MinioConfig, client


_SUPPORTED_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"
}

_REQUIRED_POINTERS = (
    "original_key",
    "text_key",
    "anonymized_key",
    "json_key",
    "editable_json_key",
)


class TeeOutput:
    def __init__(self, file_path: Union[str, Path]):
        path = Path(file_path)
        descriptor = os.open(
            os.fspath(path),
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
            0o600,
        )
        try:
            if os.name == "posix":
                os.fchmod(descriptor, 0o600)
            self.file = os.fdopen(descriptor, "w", encoding="utf-8")
        except Exception:
            os.close(descriptor)
            raise
        self.stdout = sys.stdout

    def write(self, text: str) -> int:
        self.stdout.write(text)
        self.file.write(text)
        return len(text)

    def flush(self) -> None:
        self.stdout.flush()
        self.file.flush()

    def close(self) -> None:
        if not self.file.closed:
            self.file.flush()
            self.file.close()

    def __enter__(self) -> "TeeOutput":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


def get_processable_files(input_folder: Union[str, Path]) -> List[str]:
    folder = Path(input_folder).expanduser()

    if not folder.exists():
        raise FileNotFoundError("Input folder was not found")

    if not folder.is_dir():
        raise NotADirectoryError("Input path is not a directory")

    files: List[str] = []

    for path in folder.rglob("*"):
        if (
            path.is_file()
            and not path.is_symlink()
            and path.suffix.lower() in _SUPPORTED_EXTENSIONS
        ):
            files.append(str(path.resolve()))

    return sorted(files, key=lambda value: (value.casefold(), value))


def _resolve_model_config(
    model_provider: Optional[str],
    model_name: Optional[str],
    model_base_url: Optional[str],
) -> ModelConfig:
    if any(value is not None for value in (
        model_provider, model_name, model_base_url
    )):
        return ModelConfig(
            provider=model_provider,
            model_name=model_name,
            base_url=model_base_url,
        )

    return get_model_config()


def _get_agent_output(result: Any) -> Any:
    if hasattr(result, "output"):
        return result.output

    if hasattr(result, "data"):
        return result.data

    return None


def _document_complete(record: Optional[dict]) -> bool:
    return bool(
        record
        and record.get("status") == "loinc_enriched"
        and all(record.get(pointer) for pointer in _REQUIRED_POINTERS)
    )


def _verify_completed_document(doc_id: str) -> None:
    record = get_record(doc_id)

    if not record:
        raise RuntimeError("Document record was not found after processing")

    if record.get("status") != "loinc_enriched":
        raise RuntimeError("The document pipeline did not reach its final stage")

    if not all(record.get(pointer) for pointer in _REQUIRED_POINTERS):
        raise RuntimeError("The document pipeline is missing a required storage artifact")


def _mark_incomplete_document(doc_id: Optional[str], error: Exception) -> bool:
    if not doc_id:
        return True

    try:
        record = get_record(doc_id)

        if not record or record.get("status") == "error" or _document_complete(record):
            return True

        set_error(doc_id, f"Batch processing failed ({type(error).__name__})")
        set_status(doc_id, "error")
        return True

    except Exception:
        return False


def batch_process(
    input_folder: Union[str, Path],
    language: str = "mkd+eng",
    dry_run: bool = False,
    log_file: Optional[Union[str, Path]] = None,
    model_provider: Optional[str] = None,
    model_name: Optional[str] = None,
    model_base_url: Optional[str] = None,
) -> List[dict[str, Any]]:
    if log_file is None:
        log_dir = Path("agent_logs")
        log_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        resolved_log_file = log_dir / f"batch_process_{timestamp}.log"

    else:
        resolved_log_file = Path(log_file).expanduser()
        resolved_log_file.parent.mkdir(parents=True, exist_ok=True)

    with TeeOutput(resolved_log_file) as tee:
        return _run_batch_process(
            input_folder=input_folder,
            language=language,
            dry_run=dry_run,
            log_file=resolved_log_file,
            model_provider=model_provider,
            model_name=model_name,
            model_base_url=model_base_url,
            output=tee,
        )


def _run_batch_process(
    input_folder: Union[str, Path],
    language: str,
    dry_run: bool,
    log_file: Path,
    model_provider: Optional[str],
    model_name: Optional[str],
    model_base_url: Optional[str],
    output: Any = None,
) -> List[dict[str, Any]]:
    stream = output if output is not None else sys.stdout

    def report(*parts: Any) -> None:
        print(*parts, file=stream, flush=True)

    files = get_processable_files(input_folder)

    report("=" * 60)
    report(f"Found {len(files)} supported document(s)")

    for index, filepath in enumerate(files, start=1):
        report(f"  File {index}: {Path(filepath).suffix.lower()}")

    if not files:
        report("No processable files found")
        return []

    if dry_run:
        report("Dry run mode: documents were listed but not processed")
        return []

    model_config = _resolve_model_config(
        model_provider=model_provider,
        model_name=model_name,
        model_base_url=model_base_url,
    )

    cfg = MinioConfig()
    mc = client(cfg)
    blood_agent = create_blood_agent(model_config=model_config)

    report(f"Model provider: {model_config.provider}")
    report(f"Model: {model_config.model_name}")
    report(f"OCR language: {language}")
    report("=" * 60)

    results: List[dict[str, Any]] = []

    for index, filepath in enumerate(files, start=1):
        filename = Path(filepath).name
        document_label = f"File {index}/{len(files)} ({Path(filepath).suffix.lower()})"

        report(f"Processing {document_label}")

        deps: Optional[AgentDependencies] = None

        try:
            deps = AgentDependencies(
                minio_client=mc,
                minio_config=cfg,
                filepath=filepath,
                language=language,
            )

            result = blood_agent.run_sync(
                "Process this blood test document through the complete pipeline.",
                deps=deps,
            )

            doc_id = deps.doc_id

            if not doc_id:
                raise RuntimeError("Agent finished without assigning a document ID")

            _verify_completed_document(doc_id)

            agent_output = _get_agent_output(result)

            report(f"[OK] {document_label}")
            report(f"     Document ID: {doc_id}")

            if isinstance(agent_output, str) and agent_output.strip():
                report("     Agent output: processing completed")

            results.append({
                "filename": filename,
                "success": True,
                "doc_id": doc_id,
            })

        except Exception as exc:
            doc_id = getattr(deps, "doc_id", None) if deps is not None else None
            updated = _mark_incomplete_document(doc_id, exc)
            reason = type(exc).__name__

            report(f"[FAILED] {document_label} ({reason})")

            if doc_id:
                report(f"         Document ID: {doc_id}")

            if not updated:
                report("         Warning: failed to update the document status")

            failure: dict[str, Any] = {
                "filename": filename,
                "success": False,
                "error": f"Processing failed ({reason})",
            }

            if doc_id:
                failure["doc_id"] = doc_id

            results.append(failure)

    successful = sum(bool(item["success"]) for item in results)
    failed = len(results) - successful

    report("=" * 60)
    report("SUMMARY")
    report(f"Total files: {len(results)}")
    report(f"Successful: {successful}")
    report(f"Failed: {failed}")
    report("=" * 60)
    report("Batch log completed")

    return results


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Process laboratory documents with the blood document agent"
    )

    parser.add_argument(
        "input_folder",
        type=str,
        help="Folder with PDF or image files",
    )

    parser.add_argument(
        "--language",
        type=str,
        default="mkd+eng",
        help="Tesseract OCR language or language combination",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List files without processing",
    )

    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
    )

    parser.add_argument(
        "--model-provider",
        type=str,
        choices=["openai", "anthropic", "ollama"],
        default=None,
    )

    parser.add_argument(
        "--model-name",
        type=str,
        default=None,
    )

    parser.add_argument(
        "--model-base-url",
        type=str,
        default=None,
    )

    args = parser.parse_args()

    try:
        results = batch_process(
            input_folder=args.input_folder,
            language=args.language,
            dry_run=args.dry_run,
            log_file=args.log_file,
            model_provider=args.model_provider,
            model_name=args.model_name,
            model_base_url=args.model_base_url,
        )

    except Exception as exc:
        print(
            f"Batch processing could not start ({type(exc).__name__})",
            file=sys.stderr,
        )
        return 1

    if args.dry_run:
        return 0

    return 1 if any(not item.get("success", False) for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())