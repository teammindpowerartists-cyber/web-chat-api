from pydantic import BaseModel, Field
from typing import Optional, Literal


class ChatMessageIn(BaseModel):
    session_id: str = Field(..., min_length=4, max_length=64)
    message: str = Field(..., min_length=1, max_length=2000)
    page_url: Optional[str] = None
    user_name: Optional[str] = None


class ChatMessageOut(BaseModel):
    session_id: str
    answer: str
    status: Literal["Interested", "Booked", "Spam"] = "Interested"
    service: Optional[str] = ""
    name: Optional[str] = ""


class HealthOut(BaseModel):
    status: str = "ok"
    openai_reachable: bool