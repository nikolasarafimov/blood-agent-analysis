from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class AgentResponse(BaseModel):
    doc_id: Optional[str] = None
    text_key: Optional[str] = None
    anonymized_key: Optional[str] = None
    json_key: Optional[str] = None
    loinc_key: Optional[str] = None
    output: Optional[str] = None


AgentResponseList = list[AgentResponse]