from __future__ import annotations

from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
AgentName = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")]


class Message(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role: NonEmptyText
    content: str


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    prompt: NonEmptyText
    model: Optional[NonEmptyText] = None
    system: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0, allow_inf_nan=False)
    max_tokens: Optional[int] = Field(default=None, gt=0)
    messages: Optional[list[Message]] = None
    agent_name: Optional[AgentName] = None
    memory_enabled: Optional[bool] = None


class StreamRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    prompt: NonEmptyText
    model: Optional[NonEmptyText] = None
    system: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0, allow_inf_nan=False)
    max_tokens: Optional[int] = Field(default=None, gt=0)
