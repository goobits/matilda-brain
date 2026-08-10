from __future__ import annotations

from typing import List, Optional, Union

from pydantic import BaseModel, ConfigDict


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="allow")

    message: str
    code: str
    retryable: bool


class EnvelopeBase(BaseModel):
    model_config = ConfigDict(extra="allow")

    request_id: str
    service: str
    task: str
    provider: Optional[str] = None
    model: Optional[str] = None
    result: Optional[object] = None
    usage: Optional[object] = None
    error: Optional[ErrorDetail] = None


class AskResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    text: str


class AskEnvelope(EnvelopeBase):
    result: AskResult


class StreamChunk(BaseModel):
    model_config = ConfigDict(extra="allow")

    chunk: str


class StreamDelta(BaseModel):
    model_config = ConfigDict(extra="allow")

    delta: str


class StreamDone(BaseModel):
    model_config = ConfigDict(extra="allow")

    done: bool


class StreamError(BaseModel):
    model_config = ConfigDict(extra="allow")

    message: str


class StreamEnvelope(EnvelopeBase):
    result: Union[StreamDelta, StreamDone]


class SessionSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    created_at: str
    updated_at: str
    message_count: int
    last_message: str
    model: Optional[str] = None


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


class SessionListEnvelope(EnvelopeBase):
    result: List[SessionSummary]


class SessionDetailEnvelope(EnvelopeBase):
    result: SessionDetail


class DeleteSessionResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str


class DeleteSessionEnvelope(EnvelopeBase):
    result: DeleteSessionResult


class ReloadResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    message: str


class ReloadEnvelope(EnvelopeBase):
    result: ReloadResult


class ErrorEnvelope(EnvelopeBase):
    error: ErrorDetail
