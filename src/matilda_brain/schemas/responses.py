from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="allow")

    message: str
    code: str


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str
    error: ErrorDetail


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str
    service: Optional[str] = None


class TokenUsage(BaseModel):
    model_config = ConfigDict(extra="allow")

    prompt: int
    completion: int


class AskResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    text: str
    model: Optional[str] = None
    tokens: Optional[TokenUsage] = None


class AskResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str
    result: AskResult


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


class SessionListResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str
    result: List[SessionSummary]


class SessionDetailResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str
    result: SessionDetail


class DeleteSessionResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str


class DeleteSessionResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str
    result: DeleteSessionResult


class ReloadResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    message: str


class ReloadResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str
    result: ReloadResult
