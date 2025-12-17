from pydantic import BaseModel
from typing import Optional, Any

class AgentResponse(BaseModel):
    doc_id: str
    text_key: Optional[str]
    anonymized_key: Optional[str]
    json_key: Optional[str]
    loinc_key: Optional[str]
    output: Any
