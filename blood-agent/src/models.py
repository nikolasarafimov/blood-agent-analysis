from __future__ import annotations

import re
from math import isfinite
from typing import Any, List, Literal, Optional

from minio import Minio
from pydantic import BaseModel, ConfigDict, Field, model_validator

from storage.minio_storage import MinioConfig


_NUMBER_PATTERN = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"

_NUMERIC_RE = re.compile(
    rf"^{_NUMBER_PATTERN}$"
)

_PREFIX_FLAG_RE = re.compile(
    rf"^(?P<flag>[LH])\s*:?\s*(?P<number>{_NUMBER_PATTERN})$",
    re.IGNORECASE,
)

_SUFFIX_FLAG_RE = re.compile(
    rf"^(?P<number>{_NUMBER_PATTERN})\s*(?P<flag>[LH])$",
    re.IGNORECASE,
)

_NON_FINITE_RE = re.compile(
    r"^(?:[LH]\s*:?\s*)?[+-]?(?:nan|inf|infinity)(?:\s*[LH])?$",
    re.IGNORECASE,
)


class RawText(BaseModel):
    text: str
    source_name: Optional[str] = None
    language: Optional[str] = Field(
        None,
        description="OCR language code or combination, e.g. 'eng', 'mkd', or 'mkd+eng'",
    )


class AnonymizedText(BaseModel):
    text: str


class AnonymizeResult(BaseModel):
    doc_id: str
    bronze_bucket: str
    anon_key: str
    text: str


class LabItem(BaseModel):
    row_id: Optional[str] = Field(
        None,
        description="Identifier for UI row persistence when available",
    )

    parameter: str = Field(
        ...,
        min_length=1,
        description="Laboratory test or observation name",
    )

    value: float | str = Field(
        ...,
        description=(
            "Numeric laboratory result when available. "
            "Qualitative or comparison results remain text. "
            "L/H indicators are separated into abnormal_flag."
        ),
    )

    abnormal_flag: Optional[Literal["low", "high"]] = Field(
        None,
        description=(
            "Explicit low or high indicator from the laboratory report. "
            "None means no indicator was provided."
        ),
    )

    reference_min: Optional[float] = None
    reference_max: Optional[float] = None
    unit: Optional[str] = None

    loinc_code: Optional[str] = Field(
        None,
        description="Suggested or provided LOINC code",
    )

    loinc_display: Optional[str] = Field(
        None,
        description="Suggested or provided LOINC display name",
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_measurement(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        normalized = data.copy()

        parameter = normalized.get("parameter")
        if isinstance(parameter, str):
            parameter = parameter.strip()
            if not parameter:
                raise ValueError("Laboratory parameter cannot be empty")
            normalized["parameter"] = parameter

        flag = normalized.get("abnormal_flag")
        if isinstance(flag, str):
            mapped_flag = {
                "l": "low",
                "low": "low",
                "h": "high",
                "high": "high",
            }.get(flag.strip().lower())
            if mapped_flag is not None:
                normalized["abnormal_flag"] = mapped_flag

        value = normalized.get("value")
        if isinstance(value, bool):
            raise ValueError("Laboratory result cannot be a boolean")

        if not isinstance(value, str):
            return normalized

        value = value.strip()
        if not value:
            raise ValueError("Laboratory result value must not be empty")
        if _NON_FINITE_RE.fullmatch(value):
            raise ValueError("Laboratory result value must be finite")

        flagged_match = (
            _PREFIX_FLAG_RE.fullmatch(value)
            or _SUFFIX_FLAG_RE.fullmatch(value)
        )

        if flagged_match:
            detected_flag = (
                "low" if flagged_match.group("flag").upper() == "L" else "high"
            )
            existing_flag = normalized.get("abnormal_flag")
            if existing_flag is not None and existing_flag != detected_flag:
                raise ValueError("Conflicting abnormal flags in laboratory result")
            normalized["abnormal_flag"] = detected_flag
            numeric_text = flagged_match.group("number")
        elif _NUMERIC_RE.fullmatch(value):
            numeric_text = value
        else:
            normalized["value"] = value
            return normalized

        numeric_value = float(numeric_text)
        if not isfinite(numeric_value):
            raise ValueError("Laboratory result value must be finite")

        normalized["value"] = numeric_value
        return normalized

    @model_validator(mode="after")
    def validate_measurements(self) -> "LabItem":
        if isinstance(self.value, float) and not isfinite(self.value):
            raise ValueError("Laboratory result value must be finite")

        if self.reference_min is not None and not isfinite(self.reference_min):
            raise ValueError("Reference minimum must be finite")

        if self.reference_max is not None and not isfinite(self.reference_max):
            raise ValueError("Reference maximum must be finite")

        if (
            self.reference_min is not None
            and self.reference_max is not None
            and self.reference_min > self.reference_max
        ):
            raise ValueError("Reference minimum cannot exceed reference maximum")

        return self


class LaboratoryResults(BaseModel):
    tests: List[LabItem] = Field(default_factory=list)


class AgentDependencies(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    minio_client: Minio
    minio_config: MinioConfig
    filepath: Optional[str] = None
    language: Optional[str] = None
    doc_id: Optional[str] = None

    mode: Literal[
        "ingest_only",
        "anonymize_only",
        "ingest_then_anonymize",
        "auto",
    ] = "auto"

    @model_validator(mode="after")
    def validate_document_source(self) -> "AgentDependencies":
        if not self.filepath and not self.doc_id:
            raise ValueError("Either filepath or doc_id must be provided")
        return self