from __future__ import annotations

import json
from typing import Dict, Optional, Tuple

from minio import Minio
from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_anonymizer import AnonymizerEngine

from db.sqlite_db import (
    get_record,
    set_editable_text_key,
    set_error,
    set_status,
    set_anonymized_text_pointer,
)
from src.model_config import get_model_config, ModelConfig
from src.models import AnonymizeResult, AnonymizedText
from storage.minio_storage import MinioConfig, ensure_bucket, put_anon_text


def anonymize_and_store_by_doc_id(
    mc: Minio,
    cfg: MinioConfig,
    doc_id: str,
    model_config: Optional[ModelConfig] = None,
) -> AnonymizeResult:
    rec = get_record(doc_id)
    if not rec:
        raise ValueError(f"record {doc_id} not found")

    text_key = rec.get("text_key")
    if not text_key:
        raise ValueError(f"record {doc_id} has no txt pointer yet")

    ensure_bucket(mc, cfg.bronze_bucket)
    ensure_bucket(mc, cfg.silver_bucket)

    obj = mc.get_object(cfg.bronze_bucket, text_key)
    try:
        raw_text = obj.read().decode("utf-8", errors="ignore")
    finally:
        obj.close()
        obj.release_conn()

    try:
        anon_text = anonymize_text_with_llm(raw_text, model_config=model_config)
        if isinstance(anon_text, dict):
            anon_text = json.dumps(anon_text, ensure_ascii=False)
    except Exception:
        try:
            anon_wrapped, _stats = anonymize_text(raw_text)
            anon_text = anon_wrapped.text
        except Exception as e2:
            set_error(doc_id, f"anonymize failed: {e2}")
            set_status(doc_id, "error")
            raise

    anon_key, _etag = put_anon_text(mc, cfg.silver_bucket, doc_id, anon_text)

    set_anonymized_text_pointer(doc_id, key=anon_key, bucket=cfg.silver_bucket)
    set_editable_text_key(doc_id, anon_key)
    set_status(doc_id, "anonymized")

    return AnonymizeResult(
        doc_id=doc_id,
        bronze_bucket=cfg.bronze_bucket,
        anon_key=anon_key,
        text=anon_text,
    )


def anonymize_text(text: str) -> Tuple[AnonymizedText, Dict[str, int]]:
    try:
        analyzer = AnalyzerEngine()
        anonymizer = AnonymizerEngine()

        mk_phone = Pattern(
            name="MK_PHONE",
            regex=r"\b(?:\+389|0)\s?\d{2}\s?\d{3}\s?\d{3}\b",
            score=0.7,
        )
        num_date = Pattern(
            name="NUM_DATE",
            regex=r"\b\d{1,2}[./-]\d{1,2}[./-]\d{4}\b",
            score=0.7,
        )
        txt_date = Pattern(
            name="TXT_DATE",
            regex=r"\b(?:\u0458\u0430\u043d|\u0444\u0435\u0432|\u043c\u0430\u0440|\u0430\u043f\u0440|\u043c\u0430\u0458|\u0458\u0443\u043d|\u0458\u0443\u043b|\u0430\u0432\u0433|\u0441\u0435\u043f\u0442?|\u043e\u043a\u0442|\u043d\u043e\u0435\u043c|\u0434\u0435\u043a|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{1,2},?\s+\d{4}\b",
            score=0.6,
        )
        mrn = Pattern(
            name="MEDICAL_RECORD",
            regex=r"\b(?:MRN|EMR|Record|\u0414\u043e\u0441\u0438\u0435)[\s:#-]*[A-Z\u0410-\u04280-9-]{4,}\b",
            score=0.65,
        )
        patient_line = Pattern(
            name="PATIENT_LINE",
            regex=r"^(?:Patient|\u041f\u0430\u0446\u0438\u0435\u043d\u0442|\u0418\u043c\u0435)\s*[:\-–]\s*.*$",
            score=0.9,
        )

        analyzer.registry.add_recognizer(
            PatternRecognizer(supported_entity="PHONE_NUMBER", patterns=[mk_phone])
        )
        analyzer.registry.add_recognizer(
            PatternRecognizer(supported_entity="DATE_TIME", patterns=[num_date, txt_date])
        )
        analyzer.registry.add_recognizer(
            PatternRecognizer(supported_entity="MEDICAL_RECORD", patterns=[mrn])
        )
        analyzer.registry.add_recognizer(
            PatternRecognizer(supported_entity="PATIENT_LINE", patterns=[patient_line])
        )

        results = analyzer.analyze(text=text, language="en")
        operators = {
            "DEFAULT": {"type": "replace", "new_value": "<PII>"},
            "PHONE_NUMBER": {"type": "replace", "new_value": "<PHONE>"},
            "DATE_TIME": {"type": "replace", "new_value": "<DATE>"},
            "MEDICAL_RECORD": {"type": "replace", "new_value": "<ID>"},
            "PATIENT_LINE": {"type": "replace", "new_value": "Patient: <NAME>"},
        }
        anon = anonymizer.anonymize(text=text, analyzer_results=results, operators=operators)

        stats: Dict[str, int] = {}
        for r in results:
            stats[r.entity_type] = stats.get(r.entity_type, 0) + 1

        return AnonymizedText(text=anon.text), stats

    except Exception:
        import re

        EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
        PHONE = re.compile(r"\b(?:\+389|0)\s?\d{2}\s?\d{3}\s?\d{3}\b")
        DATE1 = re.compile(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{4}\b")
        DATE2 = re.compile(
            r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s+\d{4}\b",
            re.I,
        )
        IDLIKE = re.compile(r"\b(?:ID|MRN|EMR|Patient\s*ID)[:#]?\s*[A-Z0-9-]{5,}\b", re.I)
        PATIENT_LINE = re.compile(r"^(?:Patient|\u041f\u0430\u0446\u0438\u0435\u043d\u0442)\s*[:\-]\s*.*$", re.I | re.M)

        stats = {"EMAIL": 0, "PHONE": 0, "DATE": 0, "ID": 0, "NAME": 0}

        def sub(pat, repl, s, key):
            s2, n = pat.subn(repl, s)
            stats[key] += n
            return s2

        t = text
        t = sub(EMAIL, "<EMAIL>", t, "EMAIL")
        t = sub(PHONE, "<PHONE>", t, "PHONE")
        t = sub(DATE1, "<DATE>", t, "DATE")
        t = sub(DATE2, "<DATE>", t, "DATE")
        t = sub(IDLIKE, "<ID>", t, "ID")
        t = sub(PATIENT_LINE, "Patient: <NAME>", t, "NAME")

        return AnonymizedText(text=t), stats


def _is_valid_anonymized_text(text: str, original_text: str) -> bool:
    if not text or len(text.strip()) < 10:
        return False

    tl = text.lower()
    refusal_patterns = [
        "i can't assist",
        "i cannot assist",
        "i'm unable to",
        "i am unable to",
        "i cannot help",
        "i'm not able",
        "i am not able",
        "sorry, but",
        "i apologize",
        "as an ai",
        "cannot process",
        "unable to process",
    ]
    if any(p in tl for p in refusal_patterns):
        return False

    if len(text.strip()) < len(original_text.strip()) * 0.1:
        return False

    has_numbers = any(c.isdigit() for c in text)
    medical_terms = [
        "test",
        "result",
        "value",
        "range",
        "unit",
        "hemoglobin",
        "rbc",
        "wbc",
        "platelet",
        "glucose",
        "cholesterol",
        "creatinine",
    ]
    has_medical_content = any(term in tl for term in medical_terms)

    return bool(has_numbers or has_medical_content)


def anonymize_text_with_llm(
    blood_test_text: str,
    max_retries: int = 3,
    model_config: Optional[ModelConfig] = None,
) -> str | Dict[str, str]:
    if model_config is None:
        model_config = get_model_config()

    system_prompts = [
        (
            "You are a medical data anonymization assistant. Remove ALL personally identifiable "
            "information (PII) and irrelevant metadata from the provided blood test report while "
            "preserving ALL medical data, values, units, reference ranges, and formatting. "
            "Return ONLY the anonymized text. No explanations."
        ),
        (
            "You are an anonymization system. Delete names, birth dates, addresses, phone numbers, "
            "IDs, record numbers, facility/lab names, page numbers, headers/footers. "
            "Keep every medical test name and result exactly as-is. Return ONLY anonymized text."
        ),
        "Remove PII from this medical text. Keep all medical content. Return only the anonymized text.",
    ]

    user_prompts = [
        f"""Please anonymize this blood test report.

Rules:
- Keep the text exactly as written (formatting, line breaks, test names, values, units, reference ranges).
- Remove ALL personal identifiers (names, birth dates, addresses, phone numbers, record numbers, etc.).
- Remove irrelevant metadata (laboratory names, page numbers, headers/footers).
- Do NOT summarize, reformat, or restructure.
- Output ONLY the anonymized text (no commentary).

TEXT:
{blood_test_text}
""",
        f"""Anonymize this blood test text.

Remove: names, dates of birth, IDs, addresses, phone numbers, facility/lab names, page headers/footers.
Keep: all test names, values, ranges, units, and clinical notes.

TEXT:
{blood_test_text}

Return anonymized text only.""",
        f"""Remove personal identifiers and lab identifiers from the following text, keep medical results.

{blood_test_text}""",
    ]

    last_result: Optional[str] = None

    for attempt in range(max_retries):
        system_prompt = system_prompts[min(attempt, len(system_prompts) - 1)]
        user_prompt = user_prompts[min(attempt, len(user_prompts) - 1)]
        try:
            result = model_config.chat_text(
                system=system_prompt,
                user=user_prompt,
                temperature=0,
                max_tokens=4096,
            )
            last_result = result

            if _is_valid_anonymized_text(result, blood_test_text):
                return result

            if attempt < max_retries - 1:
                continue
            return result

        except Exception as e:
            if attempt < max_retries - 1:
                continue
            raise Exception(f"Error processing with LLM after {max_retries} attempts: {str(e)}") from e

    return last_result or ""