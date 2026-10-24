from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from minio import Minio
from pydantic import ValidationError

from db.sqlite_db import (
    get_record,
    set_editable_json_key,
    set_error,
    set_status,
)
from src.model_config import ModelConfig
from src.models import LaboratoryResults
from storage.minio_storage import MinioConfig, ensure_bucket, put_json

_LOINC_CODE_PATTERN = re.compile(r"^\d{1,7}-\d$")

_CATALOG = {
    "hemoglobin": (
        "718-7",
        "Hemoglobin [Mass/volume] in Blood",
        "hemoglobin",
    ),
    "leukocytes": (
        "26464-8",
        "Leukocytes [#/volume] in Blood",
        "leukocytes",
    ),
    "neutrophils": (
        "26511-6",
        "Neutrophils/Leukocytes in Blood",
        "percentage",
    ),
    "lymphocytes": (
        "26478-8",
        "Lymphocytes/Leukocytes in Blood",
        "percentage",
    ),
    "eosinophils": (
        "26450-7",
        "Eosinophils/Leukocytes in Blood",
        "percentage",
    ),
    "monocytes": (
        "26485-3",
        "Monocytes/Leukocytes in Blood",
        "percentage",
    ),
    "basophils": (
        "30180-4",
        "Basophils/Leukocytes in Blood",
        "percentage",
    ),
    "platelets": (
        "26515-7",
        "Platelets [#/volume] in Blood",
        "platelets",
    ),
    "erythrocytes": (
        "26453-1",
        "Erythrocytes [#/volume] in Blood",
        "erythrocytes",
    ),
    "mcv": (
        "30428-7",
        "MCV [Entitic mean volume] in Red Blood Cells",
        "mcv",
    ),
    "mch": (
        "28539-5",
        "MCH [Entitic mass]",
        "mch",
    ),
    "mchc": (
        "28540-3",
        "MCHC [Entitic Mass/volume] in Red Blood Cells",
        "mchc",
    ),
}

_ALIASES = {
    "HEMOGLOBIN": "hemoglobin",
    "HAEMOGLOBIN": "hemoglobin",
    "HGB": "hemoglobin",
    "HB": "hemoglobin",
    "TOTAL LEUKOCYTE COUNT": "leukocytes",
    "TOTAL LEUCOCYTE COUNT": "leukocytes",
    "WHITE BLOOD CELL COUNT": "leukocytes",
    "WBC COUNT": "leukocytes",
    "WBC": "leukocytes",
    "NEUTROPHILS": "neutrophils",
    "NEUTROPHIL": "neutrophils",
    "LYMPHOCYTES": "lymphocytes",
    "LYMPHOCYTE": "lymphocytes",
    "EOSINOPHILS": "eosinophils",
    "EOSINOPHIL": "eosinophils",
    "MONOCYTES": "monocytes",
    "MONOCYTE": "monocytes",
    "BASOPHILS": "basophils",
    "BASOPHIL": "basophils",
    "PLATELET COUNT": "platelets",
    "PLATELETS": "platelets",
    "PLT": "platelets",
    "TOTAL RBC COUNT": "erythrocytes",
    "RBC COUNT": "erythrocytes",
    "RED BLOOD CELL COUNT": "erythrocytes",
    "ERYTHROCYTES": "erythrocytes",
    "MEAN CORPUSCULAR VOLUME MCV": "mcv",
    "MEAN CORPUSCULAR VOLUME": "mcv",
    "MCV": "mcv",
    "MEAN CELL HAEMOGLOBIN MCH": "mch",
    "MEAN CELL HEMOGLOBIN MCH": "mch",
    "MEAN CORPUSCULAR HEMOGLOBIN MCH": "mch",
    "MEAN CORPUSCULAR HAEMOGLOBIN MCH": "mch",
    "MEAN CORPUSCULAR HEMOGLOBIN": "mch",
    "MCH": "mch",
    "MEAN CELL HAEMOGLOBIN CON MCHC": "mchc",
    "MEAN CELL HEMOGLOBIN CON MCHC": "mchc",
    "MEAN CORPUSCULAR HEMOGLOBIN CONCENTRATION MCHC": "mchc",
    "MEAN CORPUSCULAR HAEMOGLOBIN CONCENTRATION MCHC": "mchc",
    "MEAN CORPUSCULAR HEMOGLOBIN CONCENTRATION": "mchc",
    "MCHC": "mchc",
}

_ALLOWED_UNITS = {
    "hemoglobin": frozenset({
        "g/dl",
        "g/l",
    }),
    "leukocytes": frozenset({
        "cumm",
        "/cumm",
        "cells/cumm",
        "cells/mm3",
        "#/mm3",
        "/mm3",
        "cells/ul",
        "#/ul",
        "10*3/ul",
        "10^3/ul",
        "10^9/l",
    }),
    "percentage": frozenset({
        "%",
        "percent",
        "percentage",
    }),
    "platelets": frozenset({
        "lakhs/cumm",
        "lakh/cumm",
        "10*5/cumm",
        "/cumm",
        "cells/cumm",
        "cells/mm3",
        "#/mm3",
        "/mm3",
        "#/ul",
        "10*3/ul",
        "10^3/ul",
        "10^9/l",
    }),
    "erythrocytes": frozenset({
        "million/cumm",
        "millions/cumm",
        "million/mm3",
        "10*6/ul",
        "10^6/ul",
        "10^12/l",
        "m/ul",
    }),
    "mcv": frozenset({
        "fl",
    }),
    "mch": frozenset({
        "pg",
    }),
    "mchc": frozenset({
        "g/dl",
        "g/l",
    }),
}


_CBC_CODE_ALIASES = {
    "WBC": "leukocytes",
    "RBC": "erythrocytes",
    "HGB": "hemoglobin",
    "HB": "hemoglobin",
    "PLT": "platelets",
    "MCV": "mcv",
    "MCH": "mch",
    "MCHC": "mchc",
    "NEUT%": "neutrophils",
    "LYM%": "lymphocytes",
    "MONO%": "monocytes",
    "EOS%": "eosinophils",
    "BASO%": "basophils",
}

_HEMOGLOBIN_LABEL = re.compile(
    r"^\s*Хемоглобин(?:\s*\((?:HGB|HB|НОВ|HOB)\))?\s*$",
    re.IGNORECASE,
)

_PAREN_CODE = re.compile(r"\(([A-Za-z]{2,8}(?:[%#])?)\)\s*$")
_SUPERSCRIPT_EXPONENT = re.compile(r"10([⁰¹²³⁴⁵⁶⁷⁸⁹]+)(?=/)")
_SUPERSCRIPT_TO_DIGIT = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")


def _normalize_parameter(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None

    original = value.strip()
    if not original:
        return None

    suffix = _PAREN_CODE.search(original)
    if suffix:
        mapped = _CBC_CODE_ALIASES.get(suffix.group(1).upper())
        if mapped is not None:
            return mapped

    mapped = _CBC_CODE_ALIASES.get(original.upper())
    if mapped is not None:
        return mapped

    normalized = re.sub(r"[^A-Z0-9]+", " ", original.upper()).strip()
    mapped = _ALIASES.get(normalized)
    if mapped is not None:
        return mapped

    if _HEMOGLOBIN_LABEL.fullmatch(original):
        return "hemoglobin"

    return None


def _normalize_unit(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None

    normalized = (
        value.strip()
        .lower()
        .replace("µ", "u")
        .replace("μ", "u")
        .replace("³", "3")
        .replace(" ", "")
    )

    normalized = _SUPERSCRIPT_EXPONENT.sub(
        lambda match: "10^" + match.group(1).translate(_SUPERSCRIPT_TO_DIGIT),
        normalized,
    )

    return normalized or None


def _is_valid_candidate_loinc_code(value: Any) -> bool:
    if not isinstance(value, str):
        return False

    code = value.strip()

    if not _LOINC_CODE_PATTERN.fullmatch(code):
        return False

    total = 0

    for position, character in enumerate(
        reversed(code.replace("-", ""))
    ):
        digit = int(character)

        if position % 2:
            digit *= 2

            if digit > 9:
                digit -= 9

        total += digit

    return total % 10 == 0


def _normalize_lab_results(obj: Any) -> dict:
    if not isinstance(obj, dict):
        raise ValueError(
            "Lab results JSON must be an object"
        )

    tests = obj.get("tests")

    if tests is None:
        tests = obj.get("results")

    if not isinstance(tests, list) or not tests:
        raise ValueError(
            "Lab results must contain a non-empty tests list"
        )

    prepared = []

    for index, test in enumerate(tests):
        if not isinstance(test, dict):
            raise ValueError(
                f"Invalid laboratory test at index {index}"
            )

        item = test.copy()

        if not item.get("parameter") and item.get("test"):
            item["parameter"] = item["test"]

        prepared.append(item)

    try:
        validated = LaboratoryResults.model_validate(
            {"tests": prepared}
        )
    except ValidationError as exc:
        raise ValueError(
            "Stored laboratory results do not match the schema"
        ) from exc

    normalized = validated.model_dump(mode="json")

    for index, test in enumerate(normalized["tests"]):
        low = test.get("reference_min")
        high = test.get("reference_max")

        if (
            low is not None
            and high is not None
            and low > high
        ):
            raise ValueError(
                f"Invalid reference interval at index {index}"
            )

    return normalized


def _has_cbc_context(tests: list[dict]) -> bool:
    recognized = {
        key
        for test in tests
        if (
            key := _normalize_parameter(
                test.get("parameter")
            )
        ) is not None
    }

    return len(recognized) >= 3


def _trusted_mapping(
    test: dict,
    has_cbc_context: bool,
) -> Optional[tuple[str, str]]:
    if not has_cbc_context:
        return None

    name = _normalize_parameter(
        test.get("parameter")
    )

    if name is None:
        return None

    code, display, unit_type = _CATALOG[name]

    unit = _normalize_unit(
        test.get("unit")
    )

    if unit not in _ALLOWED_UNITS[unit_type]:
        return None

    if not _is_valid_candidate_loinc_code(code):
        raise RuntimeError(
            "Curated LOINC catalog contains an invalid code"
        )

    return code, display


def enrich_loinc_codes_with_llm(
    lab_results: dict,
    model_config: Optional[ModelConfig] = None,
    max_retries: int = 3,
) -> dict:
    if max_retries < 1:
        raise ValueError(
            "max_retries must be at least 1"
        )

    normalized = _normalize_lab_results(
        lab_results
    )

    has_cbc_context = _has_cbc_context(
        normalized["tests"]
    )

    output = []

    for test in normalized["tests"]:
        updated = test.copy()

        trusted = _trusted_mapping(
            test,
            has_cbc_context,
        )

        if trusted is None:
            updated["loinc_code"] = None
            updated["loinc_display"] = None
        else:
            (
                updated["loinc_code"],
                updated["loinc_display"],
            ) = trusted

        output.append(updated)

    return {"tests": output}


def validate_and_enrich_loinc_codes(
    mc: Minio,
    cfg: MinioConfig,
    doc_id: str,
    model_config: Optional[ModelConfig] = None,
) -> str:
    record = get_record(doc_id)

    if not record:
        raise ValueError(
            f"record {doc_id} not found"
        )

    json_key = (
        record.get("editable_json_key")
        or record.get("json_key")
    )

    if not json_key:
        raise ValueError(
            f"record {doc_id} has no JSON pointer yet"
        )

    json_bucket = (
        record.get("json_bucket")
        or cfg.silver_bucket
    )

    try:
        obj = mc.get_object(
            json_bucket,
            json_key,
        )

        try:
            json_data = json.loads(
                obj.read().decode(
                    "utf-8",
                    errors="strict",
                )
            )
        finally:
            obj.close()
            obj.release_conn()

        enriched = enrich_loinc_codes_with_llm(
            json_data,
            model_config=model_config,
        )

        ensure_bucket(
            mc,
            json_bucket,
        )

        enriched_json_key = put_json(
            mc,
            json_bucket,
            doc_id,
            enriched,
            suffix="loinc",
        )

        set_editable_json_key(
            doc_id,
            editable_json_key=enriched_json_key,
        )

        set_error(doc_id, "")
        set_status(doc_id, "loinc_enriched")

        return enriched_json_key

    except Exception as exc:
        set_error(
            doc_id,
            f"LOINC enrichment failed: {type(exc).__name__}",
        )

        set_status(doc_id, "error")
        raise


def validate_loinc_codes_with_llm(
    lab_results: dict,
    model_config: Optional[ModelConfig] = None,
) -> dict:
    return enrich_loinc_codes_with_llm(
        lab_results,
        model_config=model_config,
    )


def get_loinc_validation_stats(
    lab_results: dict,
) -> Dict[str, int | float]:
    if not isinstance(lab_results, dict):
        tests = []
    else:
        tests = lab_results.get("tests")

        if not isinstance(tests, list):
            tests = []

    valid_tests = [
        test
        for test in tests
        if isinstance(test, dict)
    ]

    total = len(valid_tests)

    has_cbc_context = _has_cbc_context(
        valid_tests
    )

    count = sum(
        1
        for test in valid_tests
        if (
            mapping := _trusted_mapping(
                test,
                has_cbc_context,
            )
        ) is not None
        and test.get("loinc_code") == mapping[0]
    )

    return {
        "total_tests": total,
        "tests_with_loinc": count,
        "tests_without_loinc": total - count,
        "coverage_percentage": (
            round(count / total * 100, 2)
            if total
            else 0.0
        ),
    }