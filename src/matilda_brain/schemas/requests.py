from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class Message(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: str
    content: str


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    prompt: str
    model: Optional[str] = None
    system: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    messages: Optional[List[Message]] = None
    agent_name: Optional[str] = None
    memory_enabled: Optional[bool] = None


class StreamRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    prompt: str
    model: Optional[str] = None
    system: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
