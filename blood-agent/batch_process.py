import mimetypes
import os
import platform
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union

from dotenv import load_dotenv

load_dotenv()

if platform.system() == "Windows":
    poppler_path = os.getenv("POPPLER_PATH")
    if poppler_path and os.path.isdir(poppler_path):
        os.environ["PATH"] = poppler_path + os.pathsep + os.environ.get("PATH", "")

from src.models import AgentDependencies
from src.model_config import ModelConfig, get_model_config, set_model_config
from src.agent import create_blood_agent
from storage.minio_storage import MinioConfig, client


class TeeOutput:
    def __init__(self, file_path: Union[str, Path]):
        self.file = open(os.fspath(file_path), "w", encoding="utf-8")
        self.stdout = sys.stdout

    def write(self, text: str):
        self.stdout.write(text)
        self.file.write(text)
        self.file.flush()

    def flush(self):
        self.stdout.flush()
        self.file.flush()

    def close(self):
        try:
            self.file.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def get_processable_files(input_folder: Union[str, Path]) -> List[str]:
    exts = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"}
    p = Path(input_folder)

    if not p.exists():
        print(f"Error: Input folder '{p}' does not exist.")
        return []
    if not p.is_dir():
        print(f"Error: '{p}' is not a directory.")
        return []

    files: List[str] = []
    for fp in p.rglob("*"):
        if not fp.is_file():
            continue

        if fp.suffix.lower() in exts:
            files.append(str(fp))
            continue

        mime, _ = mimetypes.guess_type(str(fp))
        if mime and ("pdf" in mime or "image" in mime):
            files.append(str(fp))

    return sorted(files)


def batch_process(
    input_folder: Union[str, Path],
    language: str = "mkd+eng",
    dry_run: bool = False,
    log_file: Optional[Union[str, Path]] = None,
    model_provider: Optional[str] = None,
    model_name: Optional[str] = None,
    model_base_url: Optional[str] = None,
):
    if model_provider or model_name or model_base_url:
        model_config = ModelConfig(provider=model_provider, model_name=model_name, base_url=model_base_url)
        set_model_config(model_config)
    else:
        model_config = get_model_config()

    if log_file is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_dir = Path("agent_logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"batch_process_{ts}.log"
    else:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)

    cfg = MinioConfig()
    mc = client(cfg)

    blood_agent = create_blood_agent(model_config)

    with TeeOutput(log_file) as tee:
        original_stdout = sys.stdout
        sys.stdout = tee
        try:
            _run_batch_process(
                input_folder=str(input_folder),
                language=language,
                dry_run=dry_run,
                cfg=cfg,
                mc=mc,
                log_file=str(log_file),
                blood_agent=blood_agent,
                model_config=model_config,
            )
        finally:
            sys.stdout = original_stdout


def _run_batch_process(
    input_folder: str,
    language: str,
    dry_run: bool,
    cfg: MinioConfig,
    mc,
    log_file: str,
    blood_agent,
    model_config,
):
    print(f"Model: {model_config.provider}/{model_config.model_name}")
    print(f"Logging to: {log_file}")
    print("=" * 60)

    files = get_processable_files(input_folder)
    if not files:
        print(f"No processable files found in '{input_folder}'")
        return

    print(f"Found {len(files)} file(s) to process in '{input_folder}':")
    for i, filepath in enumerate(files, 1):
        print(f"  {i}. {Path(filepath).name}")

    if dry_run:
        print("\nDry run mode - files listed but not processed.")
        return

    print("\n" + "=" * 60)
    print(f"Running blood_agent on {len(files)} file(s)...")
    print("=" * 60 + "\n")

    results = []
    for i, filepath in enumerate(files, 1):
        print(f"\n[{i}/{len(files)}] Running agent on: {Path(filepath).name}")
        print("-" * 60)

        try:
            deps = AgentDependencies(
                minio_client=mc,
                minio_config=cfg,
                filepath=filepath,
                language=language,
            )

            result = blood_agent.run_sync("Process this blood test result.", deps=deps)

            print(f"✓ Successfully processed: {Path(filepath).name}")
            print(f"  Doc ID: {deps.doc_id}")
            print(f"  Output: {getattr(result, 'output', None)}")

            results.append({"filename": Path(filepath).name, "success": True, "doc_id": deps.doc_id})
        except Exception as e:
            print(f"✗ Failed to process: {Path(filepath).name}")
            print(f"  Error: {e}")
            print("  Traceback:")
            print(traceback.format_exc())
            results.append({"filename": Path(filepath).name, "success": False, "error": str(e)})

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total files: {len(results)}")
    print(f"Successful: {sum(1 for r in results if r['success'])}")
    print(f"Failed: {sum(1 for r in results if not r['success'])}")

    if any(not r["success"] for r in results):
        print("\nFailed files:")
        for r in results:
            if not r["success"]:
                print(f"  - {r['filename']}: {r['error']}")

    if any(r["success"] for r in results):
        print("\nSuccessfully processed files:")
        for r in results:
            if r["success"]:
                print(f"  - {r['filename']}: {r['doc_id']}")

    print("\n" + "=" * 60)
    print(f"Log saved to: {log_file}")
    print("=" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run blood_agent on multiple blood test files")
    parser.add_argument("input_folder", type=str, help="Folder with PDFs/images to process")
    parser.add_argument("--language", type=str, default="mkd+eng", help="OCR language, default mkd+eng")
    parser.add_argument("--dry-run", action="store_true", help="List files only, do not process")
    parser.add_argument("--log-file", type=str, default=None, help="Log file path (default: auto)")

    parser.add_argument("--model-provider", type=str, choices=["openai", "anthropic", "ollama"], default=None)
    parser.add_argument("--model-name", type=str, default=None)
    parser.add_argument("--model-base-url", type=str, default=None)

    args = parser.parse_args()

    batch_process(
        input_folder=args.input_folder,
        language=args.language,
        dry_run=args.dry_run,
        log_file=args.log_file,
        model_provider=args.model_provider,
        model_name=args.model_name,
        model_base_url=args.model_base_url,
    )