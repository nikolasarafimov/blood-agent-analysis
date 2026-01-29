from __future__ import annotations

import json
from typing import Any, Dict, Optional

from minio import Minio

from db.sqlite_db import (
    get_record,
    set_error,
    set_json,
    set_status,
    set_editable_json_key,
)
from src.model_config import get_model_config
from src.models import LaboratoryResults
from storage.minio_storage import MinioConfig, ensure_bucket, get_text_object, put_json


def _is_valid_json_result(result: dict) -> bool:
    """
    Checks if the JSON result appears to be valid extracted laboratory data.
    Returns True if valid, False otherwise.
    """
    if not result or not isinstance(result, dict):
        return False

    tests = result.get("tests")
    if not isinstance(tests, list) or len(tests) == 0:
        return False

    first = tests[0]
    if not isinstance(first, dict):
        return False

    if "parameter" not in first or "value" not in first:
        return False

    param_str = str(first.get("parameter", "")).lower()
    refusal_patterns = ["i can't", "i cannot", "sorry", "unable", "error", "refuse"]
    if any(p in param_str for p in refusal_patterns):
        return False

    return True


def _extract_json_from_text(s: str) -> Optional[dict]:
    """
    Best-effort: find a JSON object in a string and parse it.
    """
    if not s:
        return None
    s = s.strip()

    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass

    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    candidate = s[start : end + 1]
    try:
        obj = json.loads(candidate)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def text_to_json_with_llm(
    text: str,
    max_retries: int = 3,
    model_config=None,
) -> Dict[str, Any]:
    """
    Transform blood test text into structured JSON using LLM with retry logic.
    Returns a dict matching LaboratoryResults schema: {"tests": [ ... ]}.
    """
    if model_config is None:
        model_config = get_model_config()

    client = model_config.get_openai_client()

    system_prompts = [
        """You are a medical data extraction specialist.

Return ONLY valid JSON matching EXACTLY this schema:

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

Rules:
- Output ONE top-level key: "tests".
- No extra keys.
- No explanations, no markdown, no code fences.
- Keep units as written.
- If value is non-numeric (e.g. "<5"), keep it as string.
- If ranges like "12–16" exist, map to reference_min/reference_max.
- If multiple ranges exist (male/female), choose a general one if present; otherwise use the first.
- If you can't infer LOINC, set loinc_code/loinc_display to null.
""",
        "Extract lab results and return ONLY JSON with a top-level 'tests' array. No extra text.",
        "Return JSON only.",
    ]

    user_prompts = [
        f"Extract all lab tests from the following text and return JSON only:\n\n{text}",
        f"Return JSON with 'tests' only from this text:\n\n{text}",
        f"{text}",
    ]

    last_good: Optional[Dict[str, Any]] = None
    last_raw: Optional[str] = None
    last_err: Optional[Exception] = None

    for attempt in range(max_retries):
        try:
            system_prompt = system_prompts[min(attempt, len(system_prompts) - 1)]
            user_prompt = user_prompts[min(attempt, len(user_prompts) - 1)]

            try:
                response = client.beta.chat.completions.parse(
                    model=model_config.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format=LaboratoryResults,
                )
                parsed = response.choices[0].message.parsed
                result_dict = parsed.model_dump()
            except Exception:
                response = client.chat.completions.create(
                    model=model_config.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0,
                    max_tokens=4096,
                )
                raw = (response.choices[0].message.content or "").strip()
                last_raw = raw
                obj = _extract_json_from_text(raw)
                if obj is None:
                    raise ValueError("LLM did not return parseable JSON")
                result_dict = obj

            if _is_valid_json_result(result_dict):
                last_good = result_dict
                return result_dict

            last_good = result_dict
            if attempt < max_retries - 1:
                continue
            return result_dict

        except Exception as e:
            last_err = e
            if attempt < max_retries - 1:
                continue
            if last_good is not None:
                return last_good
            raise Exception(f"Error converting text to JSON after {max_retries} attempts: {e}") from e

    if last_good is not None:
        return last_good
    raise Exception(f"JSON extraction failed after {max_retries} attempts: {last_err}")


def parse_to_json(mc: Minio, cfg: MinioConfig, doc_id: str, model_config=None) -> str:
    """
    Picks best available text (editable -> anonymized -> extracted), converts to JSON,
    stores JSON to silver, updates DB pointers/status, returns json key.
    """
    rec = get_record(doc_id)
    if not rec:
        raise ValueError(f"record {doc_id} not found")

    text_pointer = rec.get("editable_text_key") or rec.get("anonymized_txt") or rec.get("text_key")
    if not text_pointer:
        raise ValueError(f"record {doc_id} has no text pointer yet")

    ensure_bucket(mc, cfg.bronze_bucket)
    ensure_bucket(mc, cfg.silver_bucket)

    if rec.get("editable_text_key") or rec.get("anonymized_txt"):
        text_bucket = cfg.silver_bucket
    else:
        text_bucket = cfg.bronze_bucket

    try:
        text = get_text_object(mc, text_bucket, text_pointer)
    except Exception as e:
        set_error(doc_id, f"failed reading text pointer: {e}")
        raise

    try:
        result_json = text_to_json_with_llm(text, model_config=model_config)
    except Exception as e:
        set_error(doc_id, f"serializing failed: {e}")
        raise

    json_key = put_json(mc, cfg.silver_bucket, doc_id, result_json, suffix="parsed")

    # Update DB pointers
    set_json(doc_id, result_json, bucket=cfg.silver_bucket, key=json_key)
    set_editable_json_key(doc_id, editable_json_key=json_key)
    set_status(doc_id, "json_serialized")

    return json_key