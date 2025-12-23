from pydantic import BaseModel
from typing import Optional, Any

class AgentResponse(BaseModel):
    doc_id: Optional[str] = None
    text_key: Optional[str] = None
    anonymized_key: Optional[str] = None
    json_key: Optional[str] = None
    loinc_key: Optional[str] = None
    output: Any = None