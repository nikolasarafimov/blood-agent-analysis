from __future__ import annotations

import json
import re
from typing import Dict, Any, Optional

from minio import Minio

from db.sqlite_db import get_record, set_editable_json_key, set_error, set_status
from src.model_config import get_model_config, ModelConfig
from storage.minio_storage import MinioConfig, ensure_bucket, put_json


def validate_and_enrich_loinc_codes(mc: Minio, cfg: MinioConfig, doc_id: str, model_config: Optional[ModelConfig] = None) -> str:
    rec = get_record(doc_id)
    if not rec:
        raise ValueError(f"record {doc_id} not found")

    json_key = rec.get("editable_json_key") or rec.get("json_key")
    if not json_key:
        raise ValueError(f"record {doc_id} has no JSON pointer yet")

    ensure_bucket(mc, cfg.silver_bucket)

    obj = mc.get_object(cfg.silver_bucket, json_key)
    try:
        json_data = json.loads(obj.read().decode("utf-8", errors="ignore"))
    finally:
        obj.close()
        obj.release_conn()

    try:
        normalized = _normalize_lab_results(json_data)
        enriched = validate_loinc_codes_with_llm(normalized, model_config=model_config)
    except Exception as e:
        set_error(doc_id, f"LOINC validation failed: {e}")
        raise

    enriched_json_key = put_json(mc, cfg.silver_bucket, doc_id, enriched, suffix="loinc")
    set_editable_json_key(doc_id, editable_json_key=enriched_json_key)
    set_status(doc_id, status="loinc_validated")
    return enriched_json_key


def _normalize_lab_results(obj: Any) -> dict:
    if not isinstance(obj, dict):
        raise ValueError("Lab results JSON must be an object")

    if isinstance(obj.get("tests"), list):
        tests = obj["tests"]
    elif isinstance(obj.get("results"), list):
        tests = obj["results"]
    else:
        raise ValueError("Input lab_results missing tests/results list")

    normalized = {"tests": []}
    for t in tests:
        if not isinstance(t, dict):
            continue
        normalized["tests"].append(
            {
                "parameter": t.get("parameter"),
                "value": t.get("value"),
                "reference_min": t.get("reference_min"),
                "reference_max": t.get("reference_max"),
                "unit": t.get("unit"),
                "loinc_code": t.get("loinc_code"),
                "loinc_display": t.get("loinc_display"),
            }
        )

    return normalized


def _looks_like_lab_results(obj: Any) -> bool:
    return isinstance(obj, dict) and isinstance(obj.get("tests"), list)


def _extract_json_object(text: str) -> dict:
    s = text.strip()

    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s).strip()

    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in LLM output")

    candidate = s[start : end + 1]
    obj = json.loads(candidate)
    if not isinstance(obj, dict):
        raise ValueError("Extracted JSON is not an object")
    return obj


def validate_loinc_codes_with_llm(lab_results: dict, model_config: Optional[ModelConfig] = None) -> dict:
    if model_config is None:
        model_config = get_model_config()

    if not _looks_like_lab_results(lab_results):
        raise ValueError("Input lab_results is not in expected format (missing tests list).")

    system_prompt = """You are a medical coding specialist with expertise in LOINC.
For each item in tests[], validate or fill:
- loinc_code
- loinc_display

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
- Do NOT add new keys.
- Keep existing values unchanged unless clearly wrong.
- If uncertain, set loinc_code and loinc_display to null.
- Output JSON only (no markdown, no explanation)."""

    user_prompt = f"""Validate and enrich loinc_code/loinc_display for this:

{json.dumps(lab_results, ensure_ascii=False, indent=2)}
"""

    raw = model_config.chat_text(
        system=system_prompt,
        user=user_prompt,
        temperature=0,
        max_tokens=4096,
    )
    obj = _extract_json_object(raw)

    if not _looks_like_lab_results(obj):
        raise ValueError("LLM did not return expected {tests: [...]} JSON.")

    return _normalize_lab_results(obj)


def get_loinc_validation_stats(lab_results: dict) -> Dict[str, int]:
    tests = lab_results.get("tests", []) if isinstance(lab_results, dict) else []
    total_tests = len(tests)
    tests_with_loinc = sum(1 for t in tests if isinstance(t, dict) and t.get("loinc_code"))
    tests_without_loinc = total_tests - tests_with_loinc
    return {
        "total_tests": total_tests,
        "tests_with_loinc": tests_with_loinc,
        "tests_without_loinc": tests_without_loinc,
        "coverage_percentage": round((tests_with_loinc / total_tests * 100) if total_tests else 0, 2),
    }