from __future__ import annotations

import json
from typing import Dict

from minio import Minio
from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_anonymizer import AnonymizerEngine

from db.sqlite_db import get_record, set_error, set_anonymized_txt, set_status
from src.model_config import get_model_config
from src.models import AnonymizeResult, AnonymizedText
from storage.minio_storage import MinioConfig, put_anon_text, ensure_bucket


def anonymize_and_store_by_doc_id(mc: Minio, cfg: MinioConfig, doc_id: str, model_config=None) -> AnonymizeResult:
    """
    Load TXT from bronze for doc_id, anonymize it, store anonymized TXT back to bronze,
    update DB pointer/status, and return pointers + stats.
    """
    rec = get_record(doc_id)
    if not rec:
        raise ValueError(f"record {doc_id} not found")
    text_key = rec.get("text_key")
    if not text_key:
        raise ValueError(f"record {doc_id} has no txt pointer yet")

    ensure_bucket(mc, cfg.bronze_bucket)

    # 1) read raw txt
    obj = mc.get_object(cfg.bronze_bucket, text_key)
    try:
        raw_text = obj.read().decode("utf-8", errors="ignore")
    finally:
        obj.close()
        obj.release_conn()

    # 2) anonymize
    try:
        # anon_text, stats = anonymize_text(raw_text)
        anon_text = anonymize_text_with_llm(raw_text, model_config=model_config)
    except Exception as e:
        set_error(doc_id, f"anonymize failed: {e}")
        raise

    # 3) write anonymized txt to bronze
    ensure_bucket(mc, cfg.silver_bucket)
    anon_key, etag = put_anon_text(mc, cfg.silver_bucket, doc_id, anon_text)
    # anon_key = f"documents/{doc_id}/anon_{doc_id}.txt"
    # data = anon_text.encode("utf-8")
    # mc.put_object(
    #     cfg.bronze_bucket,
    #     anon_key,
    #     io.BytesIO(data),
    #     length=len(data),
    #     content_type="text/plain; charset=utf-8",
    # )

    # 4) update DB
    set_anonymized_txt(doc_id, anonymized_txt_pointer=anon_key)
    set_status(doc_id, status="anonymized")

    return AnonymizeResult(doc_id=doc_id, bronze_bucket=cfg.bronze_bucket, anon_key=anon_key, text=anon_text)


def anonymize_text(text: str) -> tuple[AnonymizedText, Dict[str, int]]:
    """
    Try Presidio; if not installed, fall back to regex.
    Returns (anonymized_text, stats).
    """
    try:
        # --- Presidio path ---

        # Build analyzer once
        analyzer = AnalyzerEngine()
        anonymizer = AnonymizerEngine()

        # Custom MK phone, numeric & textual dates, MRN, patient line
        mk_phone = Pattern(name="MK_PHONE", regex=r"\b(?:\+389|0)\s?\d{2}\s?\d{3}\s?\d{3}\b", score=0.7)
        num_date = Pattern(name="NUM_DATE", regex=r"\b\d{1,2}[./-]\d{1,2}[./-]\d{4}\b", score=0.7)
        txt_date = Pattern(
            name="TXT_DATE",
            regex=r"\b(?:јан|фев|мар|апр|мај|јун|јул|авг|септ?|окт|ноем|дек|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{1,2},?\s+\d{4}\b",
            score=0.6,
        )
        mrn = Pattern(name="MEDICAL_RECORD", regex=r"\b(?:MRN|EMR|Record|Досие)[\s:#-]*[A-ZА-Ш0-9-]{4,}\b", score=0.65)
        patient_line = Pattern(name="PATIENT_LINE", regex=r"^(?:Patient|Пациент|Име)\s*[:\-–]\s*.*$", score=0.9)

        analyzer.registry.add_recognizer(PatternRecognizer(supported_entity="PHONE_NUMBER", patterns=[mk_phone]))
        analyzer.registry.add_recognizer(PatternRecognizer(supported_entity="DATE_TIME", patterns=[num_date, txt_date]))
        analyzer.registry.add_recognizer(PatternRecognizer(supported_entity="MEDICAL_RECORD", patterns=[mrn]))
        analyzer.registry.add_recognizer(PatternRecognizer(supported_entity="PATIENT_LINE", patterns=[patient_line]))

        # Analyze + anonymize
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
        # --- Regex fallback (lightweight) ---
        import re
        EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
        PHONE = re.compile(r"\b(?:\+389|0)\s?\d{2}\s?\d{3}\s?\d{3}\b")
        DATE1 = re.compile(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{4}\b")
        DATE2 = re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s+\d{4}\b",
                           re.I)
        IDLIKE = re.compile(r"\b(?:ID|MRN|EMR|Patient\s*ID)[:#]?\s*[A-Z0-9-]{5,}\b", re.I)
        PATIENT_LINE = re.compile(r"^(?:Patient|Пациент)\s*[:\-]\s*.*$", re.I | re.M)
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
    """
    Checks if the LLM response appears to be valid anonymized text rather than a refusal message.
    Returns True if the text seems valid, False if it looks like a refusal or error.
    """
    if not text or len(text.strip()) < 10:
        return False

    text_lower = text.lower()

    # Common refusal/error patterns
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

    # Check if the response contains refusal patterns
    for pattern in refusal_patterns:
        if pattern in text_lower:
            return False

    # Check if the response is substantially different from original (should be, after anonymization)
    # but still contains some medical content
    if len(text.strip()) < len(original_text.strip()) * 0.1:
        # Too much removed might indicate an error
        return False

    # Check for presence of medical-related content (numbers, common medical terms)
    has_numbers = any(c.isdigit() for c in text)
    medical_terms = ["test", "result", "value", "range", "unit", "hemoglobin", "rbc", "wbc", "platelet"]
    has_medical_content = any(term in text_lower for term in medical_terms)

    if not (has_numbers or has_medical_content):
        return False

    return True


def anonymize_text_with_llm(blood_test_text: str, max_retries: int = 3, model_config=None) -> dict[str, str] | str:
    """
    Use LLM to anonymize medical text with retry logic. Returns only clinical info with PII/facility data redacted.
    """
    if model_config is None:
        model_config = get_model_config()

    client = model_config.get_openai_client()

    # More explicit prompts for retries
    system_prompts = [
        """You are a medical data anonymization assistant. Your task is to remove ALL personally 
    identifiable information (PII) and irrelevant data from the provided blood test report text while preserving all medical data 
    and formatting. Return the same text with only PII and irrelevant text removed, leaving only the blood test data and results.""",
        """You are an anonymization system. Remove ALL personal identifiers (names, dates, addresses, IDs, phone numbers) 
    from the medical text while keeping ALL medical test data, values, and results intact. Return the anonymized text only, no explanations.""",
        """Remove personal identifiers from this medical text. Keep all medical content. Return only the anonymized text.""",
    ]

    base_user_prompt = """Please anonymize this blood test report. 
Keep the text exactly as it is written, including formatting, line breaks, test names, values, reference ranges, and 
physician notes about the results. Remove ALL personal identifiers (names, birth dates, addresses, phone numbers, 
record numbers, etc.) and irrelevant metadata (laboratory names, page numbers, headers/footers). Do not reformat or 
restructure. Do not omit medical content.

Text to process:
{blood_test_text}

Return the same text with personal identifiers and irrelevant metadata removed. Leave only the medical data and results."""

    user_prompts = [
        base_user_prompt.format(blood_test_text=blood_test_text),
        f"""Anonymize this blood test text. Remove names, dates, IDs, phone numbers, addresses. Keep all test names, values, and medical data.

{blood_test_text}

Return anonymized text only.""",
        f"""Remove PII from this text. Keep medical data.

{blood_test_text}""",
    ]

    for attempt in range(max_retries):
        try:
            system_prompt = system_prompts[min(attempt, len(system_prompts) - 1)]
            user_prompt = user_prompts[min(attempt, len(user_prompts) - 1)]

            response = client.chat.completions.create(
                model=model_config.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0,
                max_tokens=4096
            )

            result = response.choices[0].message.content.strip()

            # Validate the response
            if _is_valid_anonymized_text(result, blood_test_text):
                return result
            else:
                print(f"Anonymization attempt {attempt + 1}: LLM returned invalid response, retrying...")
                if attempt < max_retries - 1:
                    continue
                else:
                    # Last attempt failed validation, but return the result anyway
                    print("Warning: Anonymization validation failed, but returning result.")
                    return result

        except json.JSONDecodeError as e:
            if attempt < max_retries - 1:
                print(f"Anonymization attempt {attempt + 1}: JSON decode error, retrying...")
                continue
            # If we have a response, return it, otherwise raise
            if 'response' in locals() and response:
                return {"raw_response": response.choices[0].message.content.strip()}
            raise Exception(f"JSON decode error: {str(e)}")
        except Exception as e:
            print(f"Anonymization attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                continue
            else:
                raise Exception(f"Error processing with LLM after {max_retries} attempts: {str(e)}")

    # Should not reach here, but just in case
    raise Exception(f"Anonymization failed after {max_retries} attempts")
