from pydantic_ai import Agent, RunContext

from src.model_config import get_model_config
from src.models import AgentDependencies, AnonymizeResult
from src.tools.anonymize import anonymize_and_store_by_doc_id
from src.tools.ingest import ingest_then_extract
from src.tools.loinc_validation import validate_and_enrich_loinc_codes
from src.tools.txt_to_json import parse_to_json


def _register_tools(agent: Agent):
    """
    Register all tools on the given agent instance.
    This allows us to create agents with different model configs while keeping the same tools.
    """

    @agent.tool
    def ingest_and_extract(ctx: RunContext[AgentDependencies]) -> str:
        """
        Store original in MinIO (bronze), process it, store .txt with the SAME id,
        and return the extracted text. The MinIO .txt key is put in source_name.
        """

        if ctx.deps.doc_id is not None:
            return ctx.deps.doc_id

        # Get model config for tools
        from src.model_config import get_model_config
        model_config = get_model_config()

        ctx.deps.doc_id = ingest_then_extract(
            mc=ctx.deps.minio_client,
            cfg=ctx.deps.minio_config,
            filepath=ctx.deps.filepath,
            language=ctx.deps.language,
            model_config=model_config
        )

        return ctx.deps.doc_id

    @agent.tool
    def anonymize_txt(ctx: RunContext[AgentDependencies]) -> AnonymizeResult:
        """
        Load TXT from bronze using doc_id, anonymize it, store anonymized TXT with the same doc_id in bronze,
        update the DB pointer, and return a short status with the anonymized key in source_name.
        """

        if not getattr(ctx.deps, "doc_id", None):
            raise ValueError("ingest_and_extract must run first; no doc_id present.")

        from src.model_config import get_model_config
        model_config = get_model_config()

        res = anonymize_and_store_by_doc_id(ctx.deps.minio_client, ctx.deps.minio_config, ctx.deps.doc_id,
                                            model_config=model_config)
        return res

    @agent.tool
    def text_to_json(ctx: RunContext[AgentDependencies]) -> str:
        """
        Convert the anonymized text to structured JSON format.
        """
        if not getattr(ctx.deps, "doc_id", None):
            raise ValueError("ingest_and_extract must run first; no doc_id present.")

        from src.model_config import get_model_config
        model_config = get_model_config()

        result_json = parse_to_json(ctx.deps.minio_client, ctx.deps.minio_config, ctx.deps.doc_id,
                                    model_config=model_config)

        return result_json

    @agent.tool
    def json_to_loinc(ctx: RunContext[AgentDependencies]) -> str:
        """
        Validate and enrich the JSON with LOINC codes and semantic information.
        """
        if not getattr(ctx.deps, "doc_id", None):
            raise ValueError("text_to_json must run first; no doc_id present.")

        from src.model_config import get_model_config
        model_config = get_model_config()

        enriched_json_key = validate_and_enrich_loinc_codes(
            ctx.deps.minio_client,
            ctx.deps.minio_config,
            ctx.deps.doc_id,
            model_config=model_config
        )

        return enriched_json_key


def create_blood_agent(model_config=None):
    """
    Create the blood agent with the specified model configuration.
    If model_config is None, uses the global model configuration.
    """
    if model_config is None:
        model_config = get_model_config()

    # Get model string or object for pydantic_ai
    try:
        # Try using model string first (simpler)
        model = model_config.get_pydantic_ai_model_string()
    except Exception:
        # Fall back to model object if needed
        model = model_config.get_pydantic_ai_model()

    agent = Agent(
        model=model,
        deps_type=AgentDependencies,
        system_prompt=(
            "You are a data processing agent assigned to handle blood test results. "
            "First, convert the raw blood test data into structured, readable text and save it. "
            "Next, anonymize the saved text by removing any personally identifiable information (PII). "
            "After that, serialize the anonymized text into a structured JSON format. "
            "Finally, validate and enrich the JSON with LOINC codes and semantic information. "
            "Ensure that each task is completed in the correct order using the appropriate tools."
        ),
    )

    # Register all tools on this agent instance
    _register_tools(agent)

    return agent


# Create agent using global model config
blood_agent = create_blood_agent()
