from pathlib import Path
from dotenv import load_dotenv

from src.models import AgentDependencies
from storage.minio_storage import MinioConfig, client
from src.agent import blood_agent


def main():
    load_dotenv()

    cfg = MinioConfig()
    mc = client(cfg)

    pdf_path = Path(__file__).resolve().parent / "blood1" / "bloodanalysis.pdf"
    if not pdf_path.exists():
        raise FileNotFoundError(f"Missing test file: {pdf_path}")

    deps = AgentDependencies(
        minio_client=mc,
        minio_config=cfg,
        filepath=str(pdf_path),
        language="mkd+eng",
    )

    result = blood_agent.run_sync("Process this blood test result.", deps=deps)
    print(getattr(result, "output", result))


if __name__ == "__main__":
    main()