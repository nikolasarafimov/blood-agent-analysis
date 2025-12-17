from dotenv import load_dotenv

from src.models import AgentDependencies
from storage.minio_storage import MinioConfig, client

load_dotenv()

from src.agent import blood_agent

if __name__ == "__main__":
    load_dotenv()

    cfg = MinioConfig()
    mc = client(cfg)

    deps = AgentDependencies(
        minio_client=mc,
        minio_config=cfg,
        filepath="data/blood_test.pdf",
        language="mkd+eng",
        # doc_id='ae0d5b98-0472-47b7-9f28-e5a6b6ae4abd'
    )

    result = blood_agent.run_sync("Process this blood test result.", deps=deps)

    print(result.output)