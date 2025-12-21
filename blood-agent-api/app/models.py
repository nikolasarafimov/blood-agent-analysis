from pydantic import BaseModel
from typing import Optional, Any, Dict


class AgentResponse(BaseModel):
    doc_id: str
    text_key: Optional[str]
    anonymized_key: Optional[str]
    json_key: Optional[str]
    loinc_key: Optional[str]
    output: Any
    debug: Optional[Dict[str, Any]] = None


class Token(BaseModel):
    access_token: str
    token_type: str


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: Optional[str] = None
