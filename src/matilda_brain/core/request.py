"""Canonical request execution for routed and pre-resolved backends."""

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional, Union, cast

from ..backends import BaseBackend
from .models import AIResponse, ImageInput
from .routing import Router, router

Prompt = Union[str, List[Union[str, ImageInput]]]
BackendSpec = Union[str, BaseBackend]


@dataclass
class AIRequest:
    """Backend-independent request passed through the canonical execution path."""

    prompt: Prompt
    model: Optional[str] = None
    system: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    backend: Optional[BackendSpec] = None
    tools: Optional[List[Any]] = None
    messages: Optional[List[Dict[str, Any]]] = None
    include_messages: bool = False
    route: bool = True
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StatelessRequest:
    """Request for a single response without session state."""

    message: str
    system: Optional[str] = None
    history: List[Dict[str, str]] = field(default_factory=list)
    tools: Optional[List[Any]] = None
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2048
    timeout: int = 30
    backend: Optional[BackendSpec] = None
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StatelessResponse:
    """Serializable response returned by the stateless API."""

    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    finish_reason: str = "stop"
    usage: Optional[Dict[str, Any]] = None
    model: Optional[str] = None


def resolve_request(
    request: AIRequest,
    request_router: Optional[Router] = None,
) -> tuple[BaseBackend, Optional[str]]:
    """Resolve a routed request or validate an already-resolved request."""
    if not request.route:
        if request.backend is None or isinstance(request.backend, str):
            raise ValueError("A pre-resolved request requires a backend instance")
        return request.backend, request.model

    active_router = request_router or router
    return active_router.smart_route(
        request.prompt,
        model=request.model,
        backend=request.backend,
        **request.options,
    )


def backend_parameters(request: AIRequest, resolved_model: Optional[str]) -> Dict[str, Any]:
    """Build backend parameters once with canonical arguments taking precedence."""
    parameters = dict(request.options)
    parameters.update(
        model=resolved_model,
        system=request.system,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        tools=request.tools,
    )
    if request.include_messages:
        parameters["messages"] = request.messages
    return parameters


async def execute_request(
    request: AIRequest,
    request_router: Optional[Router] = None,
) -> AIResponse:
    """Execute a request and return its complete response."""
    response, _ = await execute_request_with_model(request, request_router)
    return response


async def execute_request_with_model(
    request: AIRequest,
    request_router: Optional[Router] = None,
) -> tuple[AIResponse, Optional[str]]:
    """Execute a request and retain the resolved model for adapters."""
    backend, resolved_model = resolve_request(request, request_router)
    response = await backend.ask(request.prompt, **backend_parameters(request, resolved_model))
    return response, resolved_model


async def stream_request(
    request: AIRequest,
    request_router: Optional[Router] = None,
) -> AsyncIterator[str]:
    """Execute a request and yield response chunks."""
    backend, resolved_model = resolve_request(request, request_router)
    async for chunk in backend.astream(request.prompt, **backend_parameters(request, resolved_model)):
        yield cast(str, chunk)
