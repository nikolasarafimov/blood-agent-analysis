from blood_agent.src.agent import blood_agent
from blood_agent.src.deps import AgentDependencies
import uuid

def run_agent_with_file(prompt: str, file_bytes: bytes, filename: str):

    doc_id = str(uuid.uuid4())

    deps = AgentDependencies(
        file_bytes=file_bytes,
        filename=filename,
        doc_id=doc_id,
        language="mkd+eng"
    )

    result = blood_agent.run_sync(prompt, deps)

    return {
        "doc_id": doc_id,
        "text_key": deps.text_key,
        "anonymized_key": deps.anonymized_key,
        "json_key": deps.json_key,
        "loinc_key": deps.loinc_key,
        "output": result.output
    }
