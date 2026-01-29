from __future__ import annotations

from typing import List, Optional, Literal

from minio import Minio
from pydantic import BaseModel, Field, ConfigDict

from storage.minio_storage import MinioConfig


class RawText(BaseModel):
    text: str
    source_name: Optional[str] = None
    language: Optional[str] = Field(None, description="ISO639 code, e.g. 'en' or 'mk'")


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
        description="Stable identifier for UI row saving. Can be null; server/DB may generate if missing.",
    )
    parameter: str = Field(..., description="E.g., 'Hemoglobin', 'RBC', 'WBC'")
    value: float | str = Field(..., description="Numeric when possible; string if truly non-numeric")
    reference_min: Optional[float] = None
    reference_max: Optional[float] = None
    unit: Optional[str] = None
    loinc_code: Optional[str] = Field(None, description="LOINC code or null")
    loinc_display: Optional[str] = None


class LaboratoryResults(BaseModel):
    tests: List[LabItem] = Field(default_factory=list)


class AgentDependencies(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    minio_client: Minio
    minio_config: MinioConfig
    filepath: Optional[str] = None
    language: Optional[str] = None
    doc_id: Optional[str] = None
    mode: Literal["ingest_only", "anonymize_only", "ingest_then_anonymize", "auto"] = "auto"