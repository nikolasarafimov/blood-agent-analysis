from minio import Minio

from db.sqlite_db import get_record, set_error, set_json, set_status, set_bucket
from src.model_config import get_model_config
from src.models import LaboratoryResults
from storage.minio_storage import MinioConfig, put_json, ensure_bucket


def _is_valid_json_result(result: dict) -> bool:
    """
    Checks if the JSON result appears to be valid extracted laboratory data.
    Returns True if valid, False otherwise.
    """
    if not result:
        return False

    # Should have a 'tests' key with a list
    if 'tests' not in result:
        return False

    tests = result.get('tests', [])
    if not isinstance(tests, list):
        return False

    # If we have at least one test with required fields, it's probably valid
    if len(tests) == 0:
        return False

    # Check if first test has required fields
    first_test = tests[0]
    if not isinstance(first_test, dict):
        return False

    # Should have at least 'parameter' and 'value'
    if 'parameter' not in first_test or 'value' not in first_test:
        return False

    # Check for refusal patterns
    param_str = str(first_test.get('parameter', '')).lower()
    refusal_patterns = ["i can't", "i cannot", "sorry", "unable", "error"]
    if any(pattern in param_str for pattern in refusal_patterns):
        return False

    return True


def text_to_json_with_llm(
        text: str,
        max_retries: int = 3,
        model_config=None
) -> dict:
    """
    Transform blood test text into structured JSON using LLM with retry logic.
    """
    if model_config is None:
        model_config = get_model_config()

    client = model_config.get_openai_client()

    # System prompts with strict schema instructions
    system_prompts = [
        """You are a medical data extraction specialist.

Your ONLY task is to extract laboratory test results from text and return strict JSON that matches EXACTLY this Pydantic schema:

LaboratoryResults:
{
  "tests": [
    {
      "parameter": string,
      "value": float | string,
      "reference_min": float | null,
      "reference_max": float | null,
      "unit": string | null,
      "loinc_code": string | null,
      "loinc_display": string | null
    }
  ]
}

RULES:
1. Always return an object with one top-level key: "tests".
2. NO explanations. NO natural language. ONLY valid JSON.
3. Convert ranges like "12–16" or "P=13.0-18.0 W=12.0-16.0" into:
   - reference_min: 13.0
   - reference_max: 18.0
4. If multiple ranges exist (male/female), choose:
   - general range if present
   - otherwise the first range.
5. Extract units exactly as written (e.g., "g/dl", "10⁹/L", "%").
6. If value is non-numeric (e.g. "<5"), return it as a string.
7. If no LOINC code is obvious, use:
   - loinc_code: null
   - loinc_display: null
8. NEVER output keys not in the schema.
9. ALWAYS output valid JSON.""",

        """Extract laboratory test results from text. 
Return structured JSON with test names, values, units, and reference ranges. 
Extract ALL tests. No explanations.""",

        """Extract lab test data from text. Return JSON with a 'tests' array."""
    ]

    user_prompts = [
        f"""Extract all laboratory test results from this text and return JSON:

{text}""",

        f"""Extract lab test results and output JSON with 'tests':

{text}""",

        f"""Extract lab tests from this text:

{text}"""
    ]

    # Retry loop
    for attempt in range(max_retries):
        try:
            system_prompt = system_prompts[min(attempt, len(system_prompts) - 1)]
            user_prompt = user_prompts[min(attempt, len(user_prompts) - 1)]

            response = client.beta.chat.completions.parse(
                model=model_config.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format=LaboratoryResults
            )

            result = response.choices[0].message.parsed
            result_dict = result.model_dump()

            if _is_valid_json_result(result_dict):
                return result_dict
            else:
                print(f"JSON extraction attempt {attempt + 1}: Invalid structure, retrying...")
                if attempt < max_retries - 1:
                    continue
                print("Warning: Validation failed, returning last result anyway.")
                return result_dict

        except Exception as e:
            print(f"JSON extraction attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                continue
            raise Exception(f"Error converting text to JSON after {max_retries} attempts: {str(e)}")

    raise Exception("JSON extraction failed after retries.")


def parse_to_json(mc: Minio, cfg: MinioConfig, doc_id: str, model_config=None) -> str:
    rec = get_record(doc_id)
    if not rec:
        raise ValueError(f"record {doc_id} not found")
    text_key = rec.get("text_key")
    if not text_key:
        raise ValueError(f"record {doc_id} has no txt pointer yet")

    # 1) read anonymized text
    ensure_bucket(mc, cfg.silver_bucket)
    obj = mc.get_object(cfg.silver_bucket, f"documents/{doc_id}/anon_{doc_id}.txt")
    try:
        anon_text = obj.read().decode("utf-8", errors="ignore")
    finally:
        obj.close()
        obj.release_conn()

    # 2) convert to JSON
    try:
        result_json = text_to_json_with_llm(anon_text, model_config=model_config)
    except Exception as e:
        set_error(doc_id, f"serializing failed: {e}")
        raise

    # 3) write JSON to MinIO
    json_key = put_json(mc, cfg.silver_bucket, doc_id, result_json)

    set_json(doc_id, json_pointer=json_key)
    set_status(doc_id, status="json_serialized")
    set_bucket(doc_id, bucket="silver")

    return json_key
