from __future__ import annotations

from pydantic_ai import Agent, RunContext

from src.model_config import ModelConfig, get_model_config
from src.models import AgentDependencies, AnonymizeResult
from src.tools.anonymize import anonymize_and_store_by_doc_id
from src.tools.loinc_validation import validate_and_enrich_loinc_codes
from src.tools.txt_to_json import parse_to_json
from src.tools.ingest import ingest_then_extract


def _register_tools(agent: Agent, model_config: ModelConfig):
    @agent.tool
    def ingest_and_extract(ctx: RunContext[AgentDependencies]) -> str:
        if getattr(ctx.deps, "doc_id", None):
            return ctx.deps.doc_id

        doc_id = ingest_then_extract(
            mc=ctx.deps.minio_client,
            cfg=ctx.deps.minio_config,
            filepath=ctx.deps.filepath,
            language=ctx.deps.language,
            model_config=model_config,
        )
        ctx.deps.doc_id = doc_id
        return doc_id

    @agent.tool
    def anonymize_txt(ctx: RunContext[AgentDependencies]) -> AnonymizeResult:
        if not getattr(ctx.deps, "doc_id", None):
            raise ValueError("ingest_and_extract must run first; no doc_id present.")

        return anonymize_and_store_by_doc_id(
            mc=ctx.deps.minio_client,
            cfg=ctx.deps.minio_config,
            doc_id=ctx.deps.doc_id,
            model_config=model_config,
        )

    @agent.tool
    def text_to_json(ctx: RunContext[AgentDependencies]) -> str:
        if not getattr(ctx.deps, "doc_id", None):
            raise ValueError("ingest_and_extract must run first; no doc_id present.")

        json_key = parse_to_json(
            mc=ctx.deps.minio_client,
            cfg=ctx.deps.minio_config,
            doc_id=ctx.deps.doc_id,
            model_config=model_config,
        )
        return json_key

    @agent.tool
    def json_to_loinc(ctx: RunContext[AgentDependencies]) -> str:
        if not getattr(ctx.deps, "doc_id", None):
            raise ValueError("ingest_and_extract must run first; no doc_id present.")

        enriched_json_key = validate_and_enrich_loinc_codes(
            mc=ctx.deps.minio_client,
            cfg=ctx.deps.minio_config,
            doc_id=ctx.deps.doc_id,
            model_config=model_config,
        )
        return enriched_json_key


def create_blood_agent(model_config: ModelConfig | None = None) -> Agent:
    if model_config is None:
        model_config = get_model_config()

    try:
        model = model_config.get_pydantic_ai_model_string()
    except Exception:
        model = model_config.get_pydantic_ai_model()

    agent = Agent(
        model=model,
        deps_type=AgentDependencies,
        system_prompt=(
            "You are a data processing agent for blood test documents.\n"
            "Run these steps in order using tools:\n"
            "1) ingest_and_extract\n"
            "2) anonymize_txt\n"
            "3) text_to_json\n"
            "4) json_to_loinc\n"
            "Use tools only."
        ),
    )

    _register_tools(agent, model_config)
    return agent


def get_blood_agent() -> Agent:
    return create_blood_agent(get_model_config())


blood_agent = get_blood_agent()