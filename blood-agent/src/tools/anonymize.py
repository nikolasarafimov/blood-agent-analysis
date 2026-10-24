from __future__ import annotations

import os
import re
from collections import Counter
from functools import lru_cache
from typing import Dict, Optional, Tuple

from minio import Minio
from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from db.sqlite_db import (
    get_record,
    set_anonymized_text_pointer,
    set_editable_anonymized_key,
    set_error,
    set_status,
)
from src.model_config import ModelConfig, get_model_config
from src.models import AnonymizeResult, AnonymizedText
from storage.minio_storage import MinioConfig, ensure_bucket, put_anon_text


_LOCAL_RULES = (
    (
        "PATIENT_LINE",
        re.compile(
            r"^[ \t]*(?:Patient(?:[ \t]+Name)?|Name|Пациент(?:[ \t]*\/?[ \t]*ка)?|"
            r"Име(?:[ \t]+и[ \t]+презиме)?)[ \t]*[:\-–][ \t]*[^\r\n]+",
            re.IGNORECASE | re.MULTILINE,
        ),
        "Patient: <NAME>",
    ),
    (
        "DOB_LINE",
        re.compile(
            r"^[ \t]*(?:Date[ \t]+of[ \t]+Birth|DOB|Birth[ \t]+Date|"
            r"Датум[ \t]+на[ \t]+раѓање|Дата[ \t]+на[ \t]+раѓање)"
            r"[ \t]*[:\-–][ \t]*[^\r\n]+",
            re.IGNORECASE | re.MULTILINE,
        ),
        "Date of birth: <DATE>",
    ),
    (
        "ADDRESS_LINE",
        re.compile(
            r"^[ \t]*(?:Address|Residence|Адреса|Живеалиште)"
            r"[ \t]*[:\-–][ \t]*[^\r\n]+",
            re.IGNORECASE | re.MULTILINE,
        ),
        "Address: <ADDRESS>",
    ),
    (
        "EMAIL_ADDRESS",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "<EMAIL>",
    ),
    (
        "PHONE_NUMBER",
        re.compile(
            r"(?<!\d)(?:\+389|00389|0)[ \t./-]?\d{2}[ \t./-]?"
            r"\d{3}[ \t./-]?\d{3}(?!\d)"
        ),
        "<PHONE>",
    ),
    (
        "MEDICAL_RECORD",
        re.compile(
            r"\b(?:MRN|EMR|Patient[ \t]*ID|Record(?:[ \t]*(?:No|Number))?|"
            r"Registration[ \t]*(?:No|Number)|Reg[ \t]*No|"
            r"Sample[ \t]*(?:No|ID)|Lab[ \t]*(?:No|ID)|"
            r"Досие|Број[ \t]+на[ \t]+досие|Матичен[ \t]+број|ЕМБГ|EMBG|JMBG)"
            r"[ \t]*[:#-]?[ \t]*[A-ZА-ЯЀ-ӿ0-9/-]{4,}\b",
            re.IGNORECASE,
        ),
        "<ID>",
    ),
    (
        "STRUCTURED_SAMPLE_ID",
        re.compile(
            r"\b(?=[A-Z0-9-]*\d)[A-Z]{2,}(?:-[A-Z0-9]{2,}){2,}\b"
        ),
        "<ID>",
    ),
    (
        "PERSON_TITLE",
        re.compile(
            r"\b(?:Mr|Mrs|Ms|Miss|Dr)\.?[ \t]+"
            r"[A-ZА-ЯЀ-ӿ][a-zа-яѐ-ӿ]+"
            r"(?:[ \t]+[A-ZА-ЯЀ-ӿ][a-zа-яѐ-ӿ]+){1,3}\b"
        ),
        "<NAME>",
    ),
    (
        "DATE_TIME",
        re.compile(r"\b\d{1,2}[./-]\d{1,2}[./-](?:\d{2}|\d{4})\b"),
        "<DATE>",
    ),
    (
        "DATE_TIME",
        re.compile(
            r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|"
            r"May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|"
            r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|"
            r"јан(?:уари)?|фев(?:руари)?|мар(?:т)?|апр(?:ил)?|"
            r"мај|јун(?:и)?|јул(?:и)?|авг(?:уст)?|сеп(?:тември)?|"
            r"окт(?:омври)?|ное(?:мври)?|дек(?:ември)?)"
            r"\.?[ \t]+\d{1,2},?[ \t]+\d{4}\b",
            re.IGNORECASE,
        ),
        "<DATE>",
    ),
)

_MEASUREMENT_PATTERN = re.compile(
    r"(?<![\w.])(?:[LH][ \t]+)?\d+(?:[.,]\d+)?[ \t]*"
    r"(?:%|g/dl|g/l|mg/dl|mmol/l|cumm|lakhs/cumm|"
    r"million/cumm|f[lL]|pg|10\^\d+/[uµμ]l)(?![A-Za-z])",
    re.IGNORECASE,
)


_CBC_CODES = (
    r"WBC|RBC|HGB|HCT|MCV|MCHC|MCH|RDW(?:-CV|-SD)?|PLT|MPV|"
    r"NEUT[%#]?|LYM[%#]?|MONO[%#]?|EOS[%#]?|BASO[%#]?"
)
_LAB_NUMBER = r"[+-]?(?:\d+(?:[.,]\d+)?|[.,]\d+)"
_LAB_UNIT = (
    r"(?:10[⁰¹²³⁴⁵⁶⁷⁸⁹^0-9]+/[uµμ]?[lL]|"
    r"[µμ]?[gmunkp]g/(?:d[lL]|[lL])|g/(?:d[lL]|[lL])|"
    r"[µμ]?[gmunkp]g|[fF][lL]|[pP][gG]|%|mmol/[lL]|"
    r"10[⁰¹²³⁴⁵⁶⁷⁸⁹^0-9]+/[uµμ]?[lL])"
)
_CBC_ROW_PATTERN = re.compile(
    rf"^(?P<label>[^\r\n]*?)(?P<code>\((?:{_CBC_CODES})\))[ \t]+"
    rf"(?:[LH][ \t]*)?(?:[<>]=?[ \t]*)?{_LAB_NUMBER}"
    rf"(?:[ \t]+{_LAB_UNIT})?"
    rf"(?:[ \t]+{_LAB_NUMBER}[ \t]*[-–—][ \t]*{_LAB_NUMBER})?"
    rf"(?:[ \t]+[LH](?=[ \t]|$))?",
    re.IGNORECASE | re.MULTILINE,
)
_PLACEHOLDER_PATTERN = re.compile(
    r"<(?:NAME|PHONE|EMAIL|ID|DATE|ADDRESS|PII)>"
)

_CBC_LABEL_ALIASES = {
    "WBC": ("Леукоцити", "Leukocytes", "White blood cells"),
    "RBC": ("Еритроцити", "Erythrocytes", "Red blood cells"),
    "HGB": ("Хемоглобин", "Hemoglobin", "Haemoglobin"),
    "HCT": ("Хематокрит", "Hematocrit", "Haematocrit"),
    "MCV": ("Среден волумен на еритроцит", "Среден волумен на Hb", "Mean corpuscular volume"),
    "MCH": ("Средна маса на Hb", "Mean corpuscular hemoglobin"),
    "MCHC": ("Средна конц. на Hb", "Mean corpuscular hemoglobin concentration"),
    "RDW-CV": ("Ширина на дистрибуција", "Red cell distribution width"),
    "PLT": ("Тромбоцити", "Platelets"),
    "MPV": ("Среден волумен на тромбоцит", "Mean platelet volume"),
    "NEUT%": ("Неутрофили", "Neutrophils"),
    "NEUT#": ("Неутрофили", "Neutrophils"),
    "LYM%": ("Лимфоцити", "Lymphocytes"),
    "LYM#": ("Лимфоцити", "Lymphocytes"),
    "MONO%": ("Моноцити", "Monocytes"),
    "MONO#": ("Моноцити", "Monocytes"),
    "EOS%": ("Еозинофили", "Eosinophils"),
    "EOS#": ("Еозинофили", "Eosinophils"),
    "BASO%": ("Базофили", "Basophils"),
    "BASO#": ("Базофили", "Basophils"),
}


def _cbc_data_spans(text: str) -> list[tuple[int, int]]:
    """Protect clinical fields without exempting unrelated PII on the same line."""
    spans = []
    for match in _CBC_ROW_PATTERN.finditer(text):
        start = match.start("code")
        label = match.group("label")
        code = match.group("code")[1:-1].upper()
        for alias in _CBC_LABEL_ALIASES.get(code, ()):
            suffix = re.search(
                rf"(?<!\w){re.escape(alias)}[ \t]*$",
                label,
                re.IGNORECASE,
            )
            if suffix:
                start = match.start("label") + suffix.start()
                break
        spans.append((start, match.end()))
    return spans


def _protected_spans(text: str) -> list[tuple[int, int]]:
    return _cbc_data_spans(text) + [
        (match.start(), match.end())
        for match in _PLACEHOLDER_PATTERN.finditer(text)
    ]


def _overlaps_protected_span(
    start: int, end: int, protected: list[tuple[int, int]]
) -> bool:
    return any(start < right and end > left for left, right in protected)


def _cbc_row_signatures(text: str) -> Counter[str]:
    return Counter(
        re.sub(r"[ \t]+", "", text[start:end]).casefold()
        for start, end in _cbc_data_spans(text)
    )


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _fallback_anonymize_text(
    text: str,
) -> Tuple[AnonymizedText, Dict[str, int]]:
    anonymized = text
    stats: Dict[str, int] = {}

    for entity, pattern, replacement in _LOCAL_RULES:
        anonymized, count = pattern.subn(replacement, anonymized)
        stats[entity] = stats.get(entity, 0) + count

    return AnonymizedText(text=anonymized), stats


@lru_cache(maxsize=1)
def _presidio_engines() -> tuple[AnalyzerEngine, AnonymizerEngine]:
    analyzer = AnalyzerEngine()
    anonymizer = AnonymizerEngine()

    for entity, pattern, _replacement in _LOCAL_RULES:
        if entity == "PERSON_TITLE":
            supported_entity = "PERSON"
        else:
            supported_entity = entity

        recognizer = PatternRecognizer(
            supported_entity=supported_entity,
            patterns=[
                Pattern(
                    name=f"LOCAL_{entity}_{len(pattern.pattern)}",
                    regex=pattern.pattern,
                    score=0.9,
                )
            ],
        )
        analyzer.registry.add_recognizer(recognizer)

    return analyzer, anonymizer


def anonymize_text(
    text: str,
) -> Tuple[AnonymizedText, Dict[str, int]]:
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    if not text.strip():
        return AnonymizedText(text=""), {}

    prepared, local_stats = _fallback_anonymize_text(text)
    expected_rows = _cbc_row_signatures(text)
    if _cbc_row_signatures(prepared.text) != expected_rows:
        raise RuntimeError("Local redaction altered laboratory measurements")

    try:
        analyzer, anonymizer = _presidio_engines()
        results = analyzer.analyze(text=prepared.text, language="en")
        protected = _protected_spans(prepared.text)
        results = [
            finding
            for finding in results
            if not _overlaps_protected_span(
                finding.start, finding.end, protected
            )
        ]
        operators = {
            "DEFAULT": OperatorConfig("replace", {"new_value": "<PII>"}),
            "PERSON": OperatorConfig("replace", {"new_value": "<NAME>"}),
            "EMAIL_ADDRESS": OperatorConfig("replace", {"new_value": "<EMAIL>"}),
            "PHONE_NUMBER": OperatorConfig("replace", {"new_value": "<PHONE>"}),
            "DATE_TIME": OperatorConfig("replace", {"new_value": "<DATE>"}),
            "MEDICAL_RECORD": OperatorConfig("replace", {"new_value": "<ID>"}),
            "PATIENT_LINE": OperatorConfig("replace", {"new_value": "Patient: <NAME>"}),
            "DOB_LINE": OperatorConfig("replace", {"new_value": "Date of birth: <DATE>"}),
            "ADDRESS_LINE": OperatorConfig("replace", {"new_value": "Address: <ADDRESS>"}),
        }
        result = anonymizer.anonymize(
            text=prepared.text,
            analyzer_results=results,
            operators=operators,
        )
    except Exception as exc:
        raise RuntimeError("Presidio PII analysis failed; anonymization was stopped") from exc

    completed, final_stats = _fallback_anonymize_text(result.text)
    if _cbc_row_signatures(completed.text) != expected_rows:
        raise RuntimeError("Anonymization altered laboratory measurements")
    stats = local_stats.copy()

    for match in results:
        stats[match.entity_type] = stats.get(match.entity_type, 0) + 1

    for entity, count in final_stats.items():
        stats[entity] = stats.get(entity, 0) + count

    return completed, stats


def _measurement_tokens(text: str) -> Counter[str]:
    return Counter(
        re.sub(r"[ \t]+", "", match.group()).lower()
        for match in _MEASUREMENT_PATTERN.finditer(text)
    )


def _is_valid_anonymized_text(text: str, original_text: str) -> bool:
    if not isinstance(text, str) or not text.strip():
        return False

    cleaned = text.strip()
    original = original_text.strip()

    if len(cleaned) < 10 or not original:
        return False

    if len(cleaned) < len(original) * 0.1:
        return False

    lowered = cleaned.lower()
    if any(
        refusal in lowered
        for refusal in (
            "i can't assist", "i cannot assist", "i'm unable to",
            "i am unable to", "i cannot help", "as an ai",
            "sorry, but", "cannot process", "unable to process",
        )
    ):
        return False

    if _measurement_tokens(cleaned) != _measurement_tokens(original):
        return False

    if _cbc_row_signatures(cleaned) != _cbc_row_signatures(original):
        return False

    residual, _residual_stats = _fallback_anonymize_text(cleaned)
    if residual.text != cleaned:
        return False

    return True


def anonymize_text_with_llm(
    blood_test_text: str,
    max_retries: int = 3,
    model_config: Optional[ModelConfig] = None,
) -> str:
    if not isinstance(blood_test_text, str):
        raise TypeError("blood_test_text must be a string")
    if not blood_test_text.strip():
        return ""
    if max_retries < 1:
        raise ValueError("max_retries must be at least 1")
    if model_config is None:
        model_config = get_model_config()

    system_prompts = (
        "You are reviewing locally redacted medical text. "
        "Remove remaining personal identifiers while retaining all "
        "test names, numeric results, units, reference ranges, "
        "and line structure unchanged. Never restore placeholders. "
        "Return only the resulting text."
    )
    user_prompt = (
        "Review the following locally redacted laboratory report. "
        "Remove residual identifying data without modifying "
        "laboratory measurements or placeholders. Return only text.\n\n"
        f"{blood_test_text}"
    )
    last_error: Optional[Exception] = None

    for _ in range(max_retries):
        try:
            candidate = model_config.chat_text(
                system=system_prompts,
                user=user_prompt,
                temperature=0,
                max_tokens=4096,
            )
            if _is_valid_anonymized_text(candidate, blood_test_text):
                return candidate.strip()
        except Exception as exc:
            last_error = exc

    if last_error is not None:
        raise RuntimeError("LLM anonymization failed") from last_error

    raise RuntimeError("LLM anonymization failed validation")


def anonymize_and_store_by_doc_id(
    mc: Minio,
    cfg: MinioConfig,
    doc_id: str,
    model_config: Optional[ModelConfig] = None,
) -> AnonymizeResult:
    record = get_record(doc_id)
    if not record:
        raise ValueError(f"record {doc_id} not found")

    text_key = record.get("text_key")
    if not text_key:
        set_error(doc_id, "Anonymization failed: extracted text is unavailable")
        set_status(doc_id, "error")
        raise ValueError(f"record {doc_id} has no text pointer")

    text_bucket = record.get("text_bucket") or cfg.bronze_bucket

    try:
        ensure_bucket(mc, text_bucket)
        ensure_bucket(mc, cfg.silver_bucket)
        obj = mc.get_object(text_bucket, text_key)
        try:
            raw_text = obj.read().decode("utf-8", errors="strict")
        finally:
            obj.close()
            obj.release_conn()

        if not raw_text.strip():
            raise ValueError("Extracted text is empty")

        anonymized, _stats = anonymize_text(raw_text)
        anon_text = anonymized.text

        if _env_flag("ENABLE_LLM_ANONYMIZATION", default=False):
            try:
                refined_text = anonymize_text_with_llm(
                    anon_text,
                    model_config=model_config,
                )
            except Exception:
                refined_text = None

            if isinstance(refined_text, str) and _is_valid_anonymized_text(
                refined_text,
                anon_text,
            ):
                anon_text = refined_text

        if not anon_text.strip():
            raise ValueError("Anonymization produced empty text")

        anon_key, _etag = put_anon_text(
            mc,
            cfg.silver_bucket,
            doc_id,
            anon_text,
        )

        set_anonymized_text_pointer(
            doc_id,
            key=anon_key,
            bucket=cfg.silver_bucket,
        )
        set_editable_anonymized_key(doc_id, anon_key)
        set_error(doc_id, "")
        set_status(doc_id, "anonymized")

        return AnonymizeResult(
            doc_id=doc_id,
            bronze_bucket=cfg.bronze_bucket,
            anon_key=anon_key,
            text=anon_text,
        )
    except Exception as exc:
        set_error(doc_id, f"Anonymization failed ({type(exc).__name__})")
        set_status(doc_id, "error")
        raise