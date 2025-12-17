import mimetypes
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

# Load environment variables before importing agent (agent needs OPENAI_API_KEY)
load_dotenv()

# --- POPPLER FIX FOR WINDOWS ---
# If running on Windows and POPPLER_PATH is provided in .env, enforce it.
import platform
if platform.system() == "Windows":
    poppler_path = os.getenv("POPPLER_PATH")
    if poppler_path and os.path.isdir(poppler_path):
        os.environ["PATH"] = poppler_path + os.pathsep + os.environ["PATH"]


from src.models import AgentDependencies
from src.model_config import ModelConfig, set_model_config, get_model_config
from src.agent import create_blood_agent
from storage.minio_storage import MinioConfig, client


class TeeOutput:
    """
    A class that writes to both stdout and a file simultaneously.
    """

    def __init__(self, file_path: str):
        self.file = open(file_path, 'w', encoding='utf-8')
        self.stdout = sys.stdout

    def write(self, text: str):
        self.stdout.write(text)
        self.file.write(text)
        self.file.flush()  # Ensure it's written immediately

    def flush(self):
        self.stdout.flush()
        self.file.flush()

    def close(self):
        if self.file:
            self.file.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def get_processable_files(input_folder: str) -> List[str]:
    """
    Find all PDF and image files in the input folder that can be processed.
    Excludes CSV and other non-image files.
    """
    processable_extensions = {'.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp'}
    files = []

    input_path = Path(input_folder)
    if not input_path.exists():
        print(f"Error: Input folder '{input_folder}' does not exist.")
        return files

    if not input_path.is_dir():
        print(f"Error: '{input_folder}' is not a directory.")
        return files

    for file_path in input_path.iterdir():
        if file_path.is_file():
            # Check by extension
            if file_path.suffix.lower() in processable_extensions:
                files.append(str(file_path))
            # Also check by MIME type as fallback
            else:
                mime, _ = mimetypes.guess_type(str(file_path))
                if mime and ('pdf' in mime or 'image' in mime):
                    files.append(str(file_path))

    return sorted(files)


def batch_process(
        input_folder: str,
        language: str = "mkd+eng",
        dry_run: bool = False,
        log_file: Optional[str] = None,
        model_provider: Optional[str] = None,
        model_name: Optional[str] = None,
        model_base_url: Optional[str] = None
):
    """
    Run the blood_agent on all processable files in the input folder.
    
    Args:
        input_folder: Path to folder containing blood test files to process
        language: Language code for OCR/text extraction (e.g., "mkd+eng", "en")
        dry_run: If True, only list files without processing them
        log_file: Path to log file (if None, auto-generates with timestamp)
        model_provider: Model provider (openai, anthropic, ollama) - overrides env var
        model_name: Model name (e.g., "gpt-4o", "claude-3-5-sonnet-20241022") - overrides env var
        model_base_url: Base URL for custom API endpoints (for Ollama, etc.) - overrides env var
    """
    # Setup model configuration
    if model_provider or model_name or model_base_url:
        model_config = ModelConfig(
            provider=model_provider,
            model_name=model_name,
            base_url=model_base_url
        )
        set_model_config(model_config)
    else:
        model_config = get_model_config()
    # Setup logging to file
    if log_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_dir = Path("agent_logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"batch_process_{timestamp}.log"
    else:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

    # Get MinIO client and config
    cfg = MinioConfig()
    mc = client(cfg)

    # Create agent with model config
    blood_agent = create_blood_agent(model_config)

    # Redirect stdout to both console and file
    with TeeOutput(log_file) as tee:
        original_stdout = sys.stdout
        sys.stdout = tee

        try:
            _run_batch_process(input_folder, language, dry_run, cfg, mc, log_file, blood_agent, model_config)
        finally:
            sys.stdout = original_stdout


def _run_batch_process(input_folder: str, language: str, dry_run: bool, cfg: MinioConfig, mc, log_file: str,
                       blood_agent, model_config):
    """
    Internal function that does the actual batch processing.
    All print statements here will be logged to both console and file.
    """
    print(f"Model: {model_config.provider}/{model_config.model_name}")
    print(f"Logging to: {log_file}")
    print("=" * 60)

    # Find all processable files
    files = get_processable_files(input_folder)

    if not files:
        print(f"No processable files found in '{input_folder}'")
        return

    print(f"Found {len(files)} file(s) to process in '{input_folder}':")
    for i, filepath in enumerate(files, 1):
        print(f"  {i}. {os.path.basename(filepath)}")

    if dry_run:
        print("\nDry run mode - files listed but not processed.")
        return

    # Run agent on each file
    print(f"\n{'=' * 60}")
    print(f"Running blood_agent on {len(files)} file(s)...")
    print(f"{'=' * 60}\n")

    results = []
    for i, filepath in enumerate(files, 1):
        print(f"\n[{i}/{len(files)}] Running agent on: {os.path.basename(filepath)}")
        print("-" * 60)

        try:
            deps = AgentDependencies(
                minio_client=mc,
                minio_config=cfg,
                filepath=filepath,
                language=language,
            )

            # Run the agent (same as in demo.py)
            result = blood_agent.run_sync("Process this blood test result.", deps=deps)

            print(f"✓ Successfully processed: {os.path.basename(filepath)}")
            print(f"  Doc ID: {deps.doc_id}")
            print(f"  Output: {result.output}")

            results.append({
                "filename": os.path.basename(filepath),
                "success": True,
                "doc_id": deps.doc_id
            })

        except Exception as e:
            print(f"✗ Failed to process: {os.path.basename(filepath)}")
            print(f"  Error: {e}")
            results.append({
                "filename": os.path.basename(filepath),
                "success": False,
                "error": str(e)
            })

    # Print summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    print(f"Total files: {len(results)}")
    print(f"Successful: {sum(1 for r in results if r['success'])}")
    print(f"Failed: {sum(1 for r in results if not r['success'])}")

    if any(not r['success'] for r in results):
        print(f"\nFailed files:")
        for r in results:
            if not r['success']:
                print(f"  - {r['filename']}: {r['error']}")

    if any(r['success'] for r in results):
        print(f"\nSuccessfully processed files:")
        for r in results:
            if r['success']:
                print(f"  - {r['filename']}: {r['doc_id']}")

    print(f"\n{'=' * 60}")
    print(f"Log saved to: {log_file}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Run blood_agent on multiple blood test files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python batch_process.py /path/to/blood_tests
  python batch_process.py /path/to/blood_tests --language en
  python batch_process.py /path/to/blood_tests --dry-run
        """
    )
    parser.add_argument(
        "input_folder",
        type=str,
        help="Path to folder containing blood test files (PDFs and images) to process"
    )
    parser.add_argument(
        "--language",
        type=str,
        default="mkd+eng",
        help="Language code for OCR/text extraction (default: 'mkd+eng')"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List files without processing them"
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Path to log file (default: auto-generated with timestamp)"
    )
    parser.add_argument(
        "--model-provider",
        type=str,
        choices=["openai", "anthropic", "ollama"],
        default=None,
        help="Model provider (openai, anthropic, ollama). Defaults to MODEL_PROVIDER env var or 'openai'"
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default=None,
        help="Model name (e.g., 'gpt-4o', 'claude-3-5-sonnet-20241022', 'llama3.3:70b'). Defaults to MODEL_NAME env var or 'gpt-4o'"
    )
    parser.add_argument(
        "--model-base-url",
        type=str,
        default=None,
        help="Base URL for model API (required for Ollama, optional for others). Defaults to MODEL_BASE_URL env var"
    )

    args = parser.parse_args()

    batch_process(
        input_folder=args.input_folder,
        language=args.language,
        dry_run=args.dry_run,
        log_file=args.log_file,
        model_provider=args.model_provider,
        model_name=args.model_name,
        model_base_url=args.model_base_url
    )
