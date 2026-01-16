from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    error: str


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str
    service: Optional[str] = None


class TokenUsage(BaseModel):
    model_config = ConfigDict(extra="allow")

    prompt: int
    completion: int


class AskResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    text: str
    model: Optional[str] = None
    tokens: Optional[TokenUsage] = None


class StreamChunk(BaseModel):
    model_config = ConfigDict(extra="allow")

    chunk: str


class StreamDone(BaseModel):
    model_config = ConfigDict(extra="allow")

    done: bool


class StreamError(BaseModel):
    model_config = ConfigDict(extra="allow")

    error: str


class SessionSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    created_at: str
    updated_at: str
    message_count: int
    last_message: str
    model: str


class SessionMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: str
    content: str
    timestamp: str
    model: Optional[str] = None


class SessionDetail(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    created_at: str
    updated_at: str
    messages: List[SessionMessage]
    model: Optional[str] = None
    system_prompt: Optional[str] = None
    tools: Optional[List[str]] = None


class DeleteSessionResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str
    id: str


class ReloadResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str
    message: str
