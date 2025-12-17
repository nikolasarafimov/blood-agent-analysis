from typing import List, Optional, TypedDict, Literal

from minio import Minio
from pydantic import BaseModel, Field

from storage.minio_storage import MinioConfig


class RawText(BaseModel):
    text: str
    source_name: Optional[str] = None
    language: Optional[str] = Field(None, description="iso639, e.g., 'en' or 'mk'")
    # doc_id: str | None

class AnonymizedText(BaseModel):
    text: str
class AnonymizeResult(TypedDict):
    doc_id: str
    bronze_bucket: str
    anon_key: str
    # redactions: int
    # stats: Dict[str, int]
    text: str


class LabObservation(BaseModel):
    parameter: str  # e.g., "Hemoglobin"
    value: float | str  # sometimes "<5"
    unit: Optional[str]  # g/dL
    ref_range: Optional[str]  # e.g., "12-16"
    flags: Optional[str]  # H/L
    language: Optional[str] = None


class LabDoc(BaseModel):
    items: List[LabObservation]


class LoincMappedItem(BaseModel):
    parameter: str
    loinc_code: Optional[str]
    loinc_long_name: Optional[str]
    class_name: Optional[str]  # LOINC class (e.g., HEM/BC)
    unit: Optional[str]
    value: float | str
    ref_range: Optional[str]
    flags: Optional[str]


class LoincDoc(BaseModel):
    items: List[LoincMappedItem]


class LabItem(BaseModel):
    parameter: str = Field(..., description="E.g., 'Haemoglobin', 'RBC', 'WBC'")
    value: float | str = Field(..., description="Numeric value when possible; string if truly non-numeric")
    reference_min: Optional[float] = None
    reference_max: Optional[float] = None
    unit: Optional[str] = None
    loinc_code: Optional[str] = Field(None, description="Chosen LOINC code from allowed list, or null if none fits")
    loinc_display: Optional[str] = None


class LaboratoryResults(BaseModel):
    tests: List[LabItem] = Field(default_factory=list)


class AgentDependencies(BaseModel):
    minio_client: Minio
    minio_config: MinioConfig
    filepath: Optional[str] = None        # If you have a file that needs OCR first
    language: Optional[str] = None
    doc_id: Optional[str] = None          # If you already have a stored TXT

    # Control which stage(s) to run
    mode: Literal["ingest_only", "anonymize_only", "ingest_then_anonymize", "auto"] = "auto"

    class Config:
        # This allows Pydantic to handle non-Pydantic types like the Minio client
        arbitrary_types_allowed = True

# class PipelineResult(BaseModel):
#     doc_id: str
#     txt_key: Optional[str] = None
#     anonymized_key: Optional[str] = None
#     redactions: int = 0
#     preview: Optional[str] = None
#     issues: List[str] = Field(default_factory=list)


# class ExtractWithHintsDeps(DocIdDeps):
#     # optional LOINC suggestions: {"Hemoglobin":[{"code":"718-7","display":"..."}, ...], ...}
#     suggestions: dict | None = None

# class IngestResult(NamedTuple):
#     doc_id: str
#     bucket: str
#     original_key: str
#     text_key: str
#     text: str
#     language: Optional[str]
