from __future__ import annotations

import json
from typing import Dict

from minio import Minio

from db.sqlite_db import get_record, set_error, set_status
from src.model_config import get_model_config
from src.models import LaboratoryResults, LoincMappedItem, LoincDoc
from storage.minio_storage import MinioConfig, put_json, ensure_bucket


def validate_and_enrich_loinc_codes(mc: Minio, cfg: MinioConfig, doc_id: str, model_config=None) -> str:
    """
    Load JSON from silver bucket, validate and enrich LOINC codes, 
    store enriched JSON back to silver bucket.
    """
    rec = get_record(doc_id)
    if not rec:
        raise ValueError(f"record {doc_id} not found")

    json_key = rec.get("lab_items")
    if not json_key:
        raise ValueError(f"record {doc_id} has no JSON pointer yet")

    # 1) read JSON from silver
    ensure_bucket(mc, cfg.silver_bucket)
    obj = mc.get_object(cfg.silver_bucket, json_key)
    try:
        json_data = json.loads(obj.read().decode("utf-8"))
    finally:
        obj.close()
        obj.release_conn()

    # 2) validate and enrich LOINC codes
    try:
        enriched_data = validate_loinc_codes_with_llm(json_data, model_config=model_config)
    except Exception as e:
        set_error(doc_id, f"LOINC validation failed: {e}")
        raise

    # 3) write enriched JSON to silver
    enriched_json_key = put_json(mc, cfg.silver_bucket, doc_id, enriched_data)

    set_status(doc_id, status="loinc_validated")
    return enriched_json_key


def validate_loinc_codes_with_llm(lab_results: dict, model_config=None) -> dict:
    """
    Use LLM to validate and enrich LOINC codes for laboratory results.
    """
    if model_config is None:
        model_config = get_model_config()

    client = model_config.get_openai_client()

    system_prompt = """You are a medical coding specialist with expertise in LOINC (Logical Observation Identifiers Names and Codes). 
    Your task is to validate and enrich laboratory test results with accurate LOINC codes and semantic information.

    Instructions:
    1. Review each test parameter and its current LOINC code (if any)
    2. Validate that the LOINC code matches the test parameter correctly
    3. If no LOINC code exists or it's incorrect, suggest the most appropriate one
    4. Add LOINC display names and semantic class information
    5. Ensure units are consistent with LOINC standards
    6. Flag any parameters that cannot be reliably mapped to LOINC

    Common LOINC codes for blood tests:
    - Hemoglobin: 718-7 (Hemoglobin [Mass/volume] in Blood)
    - Hematocrit: 4544-3 (Hematocrit [Volume fraction] of Blood)
    - White Blood Cell Count: 6690-2 (Leukocytes [#/volume] in Blood)
    - Red Blood Cell Count: 789-8 (Erythrocytes [#/volume] in Blood)
    - Platelet Count: 777-3 (Platelets [#/volume] in Blood)
    - Glucose: 33747-0 (Glucose [Mass/volume] in Blood)
    - Total Cholesterol: 2093-3 (Cholesterol [Mass/volume] in Serum or Plasma)
    - HDL Cholesterol: 2085-9 (Cholesterol in HDL [Mass/volume] in Serum or Plasma)
    - LDL Cholesterol: 2089-1 (Cholesterol in LDL [Mass/volume] in Serum or Plasma)
    - Triglycerides: 2571-8 (Triglyceride [Mass/volume] in Serum or Plasma)

    Return the enriched data with validated LOINC information."""

    user_prompt = f"""Please validate and enrich the LOINC codes for these laboratory results:

    {json.dumps(lab_results, indent=2)}

    For each test parameter:
    1. Validate the existing LOINC code (if present)
    2. Add or correct LOINC code if needed
    3. Add LOINC display name
    4. Add semantic class (e.g., HEM/BC for hematology, CHEM for chemistry)
    5. Ensure units are LOINC-compliant
    6. Mark confidence level for the mapping

    Return the enriched laboratory results with validated LOINC information."""

    response = client.beta.chat.completions.parse(
        model=model_config.model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        response_format=LaboratoryResults
    )

    result = response.choices[0].message.parsed
    return result.model_dump()


def create_loinc_mapped_doc(lab_results: dict) -> LoincDoc:
    """
    Convert LaboratoryResults to LoincDoc format with enriched LOINC information.
    """
    loinc_items = []

    for test in lab_results.get("tests", []):
        loinc_item = LoincMappedItem(
            parameter=test.get("parameter", ""),
            value=test.get("value"),
            unit=test.get("unit"),
            ref_range=test.get("reference_min") and test.get("reference_max") and
                      f"{test.get('reference_min')}-{test.get('reference_max')}",
            flags=None,  # Could be derived from reference ranges
            loinc_code=test.get("loinc_code"),
            loinc_long_name=test.get("loinc_display"),
            class_name=None  # Could be derived from LOINC code
        )
        loinc_items.append(loinc_item)

    return LoincDoc(items=loinc_items)


def get_loinc_validation_stats(lab_results: dict) -> Dict[str, int]:
    """
    Generate statistics about LOINC code coverage and validation.
    """
    total_tests = len(lab_results.get("tests", []))
    tests_with_loinc = sum(1 for test in lab_results.get("tests", [])
                           if test.get("loinc_code"))
    tests_without_loinc = total_tests - tests_with_loinc

    return {
        "total_tests": total_tests,
        "tests_with_loinc": tests_with_loinc,
        "tests_without_loinc": tests_without_loinc,
        "coverage_percentage": round((tests_with_loinc / total_tests * 100) if total_tests > 0 else 0, 2)
    }
