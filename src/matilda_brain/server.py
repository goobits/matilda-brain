"""
HTTP server for the Matilda Brain API.

Exposes Brain functionality over HTTP for browser-based clients.
Supports both one-shot requests and streaming responses with conversation memory.

Usage:
    brain serve --port 8772

    # Or directly:
    python -m matilda_brain.server --port 8772
"""

import argparse
import asyncio
import json
import os
import secrets
import uuid
from collections.abc import Mapping
from contextlib import suppress
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Optional, Sequence, TypeVar

from aiohttp import web
from aiohttp.typedefs import Handler, Middleware
from aiohttp.web import Request, Response, StreamResponse
from matilda_transport import (
    build_envelope,
    ensure_pipe_supported,
    prepare_unix_socket,
    resolve_transport,
)
from pydantic import BaseModel, TypeAdapter
from pydantic import ValidationError as PydanticValidationError

from .core.api import stream_async
from .core.exceptions import (
    APIKeyError,
    BackendError,
    BackendTimeoutError,
    ConfigurationError,
    ModelError,
    QuotaExceededError,
    RateLimitError,
)
from .core.exceptions import (
    ValidationError as BrainValidationError,
)
from .internal.security import get_allowed_origins, is_origin_allowed
from .internal.token_storage import get_or_create_token
from .internal.utils import get_logger
from .schemas.requests import AgentName, AskRequest, StreamRequest
from .schemas.responses import (
    AskEnvelope,
    DeleteSessionEnvelope,
    ErrorEnvelope,
    ReloadEnvelope,
    SessionDetailEnvelope,
    SessionListEnvelope,
    StreamEnvelope,
)
from .session.chat import PersistentChatSession
from .session.manager import ChatSessionManager

logger = get_logger(__name__)
RequestModel = TypeVar("RequestModel", bound=BaseModel)
ResponseType = TypeVar("ResponseType", bound=StreamResponse)
AGENT_NAME_ADAPTER = TypeAdapter(AgentName)
ALLOWED_ORIGINS_CONTEXT: ContextVar[Sequence[str]] = ContextVar("allowed_origins", default=())

# Shared session manager instance
_session_manager: Optional[ChatSessionManager] = None


def security_middleware(api_token: str, allowed_origins: Sequence[str]) -> Middleware:
    """Create request-scoped authentication and CORS policy middleware."""

    @web.middleware
    async def middleware(request: Request, handler: Handler) -> StreamResponse:
        context_token = ALLOWED_ORIGINS_CONTEXT.set(allowed_origins)
        try:
            if request.path in {"/", "/health"} or request.method == "OPTIONS":
                return await handler(request)

            parts = request.headers.get("Authorization", "").split()
            if len(parts) != 2 or parts[0].casefold() != "bearer":
                return error_response(
                    "Unauthorized: Missing or invalid Authorization header",
                    request,
                    status=401,
                    code="unauthorized",
                    task="auth",
                )
            if not secrets.compare_digest(parts[1], api_token):
                return error_response("Forbidden: Invalid token", request, status=403, code="forbidden", task="auth")
            return await handler(request)
        finally:
            ALLOWED_ORIGINS_CONTEXT.reset(context_token)

    return middleware


def get_session_manager() -> ChatSessionManager:
    """Get or create the session manager singleton."""
    global _session_manager
    if _session_manager is None:
        _session_manager = ChatSessionManager()
    return _session_manager


def add_cors_headers(response: ResponseType, request: Optional[Request] = None) -> ResponseType:
    """Add cross-origin headers when the request origin is explicitly allowed."""
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"

    if request:
        req_origin = request.headers.get("Origin")
        allowed_origins = ALLOWED_ORIGINS_CONTEXT.get()
        if req_origin and is_origin_allowed(req_origin, list(allowed_origins)):
            response.headers["Access-Control-Allow-Origin"] = req_origin
            response.headers["Vary"] = "Origin"

    return response


def should_validate() -> bool:
    return os.getenv("MATILDA_SCHEMA_VALIDATE", "").lower() in {"1", "true", "yes", "on"}


def validate_response(model: type[BaseModel], payload: Mapping[str, Any]) -> None:
    if not should_validate():
        return
    model.model_validate(payload)


def ok_response(
    task: str,
    payload: Any,
    request: Request,
    schema_model: Optional[type[BaseModel]] = None,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    usage: Optional[dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> Response:
    response_payload = build_envelope(
        request_id=request_id or str(uuid.uuid4()),
        service="brain",
        task=task,
        provider=provider,
        model=model_name,
        result=payload,
        usage=usage,
    )
    if schema_model is not None:
        validate_response(schema_model, response_payload)
    return add_cors_headers(web.json_response(response_payload), request)


def error_response(
    message: str,
    request: Request,
    status: int = 400,
    code: str = "bad_request",
    task: str = "unknown",
    request_id: Optional[str] = None,
    retryable: Optional[bool] = None,
) -> Response:
    response_payload = build_envelope(
        request_id=request_id or str(uuid.uuid4()),
        service="brain",
        task=task,
        error={
            "message": message,
            "code": code,
            "retryable": status >= 500 or status == 429 if retryable is None else retryable,
        },
    )
    validate_response(ErrorEnvelope, response_payload)
    return add_cors_headers(web.json_response(response_payload, status=status), request)


def execution_error_details(error: Exception) -> tuple[str, int, str]:
    if isinstance(error, BrainValidationError):
        return str(error), 400, "invalid_request"
    if isinstance(error, ModelError):
        return str(error), 400, "invalid_model"
    if isinstance(error, (RateLimitError, QuotaExceededError)):
        return str(error), 429, "rate_limited"
    if isinstance(error, BackendTimeoutError):
        return "AI backend timed out", 504, "backend_timeout"
    if isinstance(error, APIKeyError):
        return str(error), 503, "backend_unavailable"
    if isinstance(error, (BackendError, ConfigurationError)):
        return "AI backend is unavailable", 503, "backend_unavailable"
    return "Internal server error", 500, "internal_error"


def execution_error_response(error: Exception, request: Request, task: str) -> Response:
    """Map expected AI failures to stable, non-sensitive HTTP errors."""
    message, status, code = execution_error_details(error)
    return error_response(message, request, status=status, code=code, task=task)


def validation_error_message(error: PydanticValidationError) -> str:
    issues = []
    for detail in error.errors(include_input=False, include_url=False):
        location = ".".join(str(part) for part in detail["loc"])
        issues.append(f"{location}: {detail['msg']}" if location else detail["msg"])
    return "Invalid request: " + "; ".join(issues)


async def parse_json_request(
    request: Request,
    schema: type[RequestModel],
    task: str,
) -> tuple[Optional[RequestModel], Optional[Response]]:
    try:
        data = await request.json()
    except web.HTTPRequestEntityTooLarge:
        return None, error_response("Request body too large", request, status=413, code="request_too_large", task=task)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return None, error_response("Invalid JSON", request, task=task)

    if not isinstance(data, dict):
        return None, error_response("Request body must be a JSON object", request, task=task)

    try:
        return schema.model_validate(data), None
    except PydanticValidationError as error:
        return None, error_response(validation_error_message(error), request, code="invalid_request", task=task)


async def handle_options(request: Request) -> Response:
    """Handle CORS preflight requests."""
    return add_cors_headers(Response(status=200), request)


async def handle_health(request: Request) -> Response:
    """Health check endpoint."""
    return ok_response("health", {"status": "ok", "service": "brain"}, request)


async def handle_ask(request: Request) -> Response:
    """Handle a validated AI request with optional conversation history."""
    request_data, validation_error = await parse_json_request(request, AskRequest, "ask")
    if validation_error is not None:
        return validation_error
    assert request_data is not None

    agent_name = request.headers.get("X-Agent-Name") or request_data.agent_name or "assistant"
    try:
        agent_name = AGENT_NAME_ADAPTER.validate_python(agent_name)
    except PydanticValidationError:
        return error_response("Invalid X-Agent-Name header", request, code="invalid_request", task="ask")

    messages = request_data.messages or []
    system = request_data.system
    memory_enabled = request_data.memory_enabled if "memory_enabled" in request_data.model_fields_set else True

    try:
        if system is None and messages:
            for msg in messages:
                if msg.role == "system":
                    system = msg.content
                    break

        timestamp = datetime.now(timezone.utc).isoformat()
        history_messages = [
            {"role": message.role, "content": message.content, "timestamp": timestamp}
            for message in messages
            if message.role != "system"
        ]

        async with PersistentChatSession(
            system=system,
            model=request_data.model,
            agent_name=agent_name,
            memory_enabled=memory_enabled,
        ) as session:
            session.history = history_messages
            response = await session.ask_async(
                request_data.prompt,
                model=request_data.model,
                temperature=request_data.temperature,
                max_tokens=request_data.max_tokens,
            )

        provider = response.metadata.get("provider") or response.backend
        usage = (
            {"prompt": response.tokens_in or 0, "completion": response.tokens_out or 0}
            if response.tokens_in is not None or response.tokens_out is not None
            else None
        )

        return ok_response(
            "ask",
            {"text": str(response)},
            request,
            schema_model=AskEnvelope,
            provider=provider,
            model_name=response.model,
            usage=usage,
        )

    except Exception as error:
        logger.exception("Error processing request")
        return execution_error_response(error, request, "ask")


def stream_payload(
    request_id: str,
    model: Optional[str],
    *,
    result: Optional[dict[str, Any]] = None,
    error: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    return {
        "capability": "reason-over-context",
        **build_envelope(
            request_id=request_id,
            service="brain",
            task="stream",
            model=model,
            result=result,
            error=error,
        ),
    }


async def write_sse_event(
    response: StreamResponse,
    payload: dict[str, Any],
    schema: type[BaseModel],
) -> None:
    validate_response(schema, payload)
    event = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    await response.write(f"data: {event}\n\n".encode())


async def handle_stream(request: Request) -> StreamResponse:
    """Stream a validated AI request as server-sent events."""
    request_data, validation_error = await parse_json_request(request, StreamRequest, "stream")
    if validation_error is not None:
        return validation_error
    assert request_data is not None

    request_id = str(uuid.uuid4())
    response = add_cors_headers(
        StreamResponse(
            status=200,
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        ),
        request,
    )
    await response.prepare(request)

    try:
        async for chunk in stream_async(
            request_data.prompt,
            model=request_data.model,
            system=request_data.system,
            temperature=request_data.temperature,
            max_tokens=request_data.max_tokens,
        ):
            await write_sse_event(
                response,
                stream_payload(request_id, request_data.model, result={"delta": chunk}),
                StreamEnvelope,
            )
        await write_sse_event(
            response,
            stream_payload(request_id, request_data.model, result={"done": True}),
            StreamEnvelope,
        )
    except ConnectionResetError:
        logger.info("Streaming client disconnected")
    except Exception as error:
        logger.exception("Error during streaming")
        message, status, code = execution_error_details(error)
        error_payload = stream_payload(
            request_id,
            request_data.model,
            error={"message": message, "code": code, "retryable": status >= 500 or status == 429},
        )
        with suppress(ConnectionResetError, RuntimeError):
            await write_sse_event(response, error_payload, ErrorEnvelope)
    finally:
        with suppress(ConnectionResetError, RuntimeError):
            await response.write_eof()
    return response


async def handle_list_sessions(request: Request) -> Response:
    """List persisted chat sessions."""
    try:
        manager = get_session_manager()
        sessions = manager.list_sessions()
        return ok_response("sessions", sessions, request, schema_model=SessionListEnvelope)
    except Exception as error:
        logger.exception("Error listing sessions")
        return execution_error_response(error, request, "sessions")


async def handle_get_session(request: Request) -> Response:
    """Return one persisted chat session."""
    session_id = request.match_info.get("id")
    if not session_id:
        return error_response("Missing session ID", request, task="session")

    try:
        manager = get_session_manager()
        session = manager.load_session(session_id)

        if session is None:
            return error_response(
                f"Session '{session_id}' not found", request, status=404, code="not_found", task="session"
            )

        return ok_response("session", session.to_dict(), request, schema_model=SessionDetailEnvelope)
    except Exception as error:
        logger.exception("Error loading session %s", session_id)
        return execution_error_response(error, request, "session")


async def handle_delete_session(request: Request) -> Response:
    """Delete one persisted chat session."""
    session_id = request.match_info.get("id")
    if not session_id:
        return error_response("Missing session ID", request, task="delete_session")

    try:
        manager = get_session_manager()
        deleted = manager.delete_session(session_id)

        if deleted:
            return ok_response("delete_session", {"id": session_id}, request, schema_model=DeleteSessionEnvelope)
        return error_response(
            f"Session '{session_id}' not found", request, status=404, code="not_found", task="delete_session"
        )
    except Exception as error:
        logger.exception("Error deleting session %s", session_id)
        return execution_error_response(error, request, "delete_session")


async def handle_reload(request: Request) -> Response:
    """Reload configuration from disk."""
    try:
        from .config.schema import load_config, set_config

        # Reload configuration from file
        new_config = load_config()
        # Update global config state
        set_config(new_config)

        logger.info("Configuration reloaded via API")
        return ok_response("reload", {"message": "Configuration reloaded"}, request, schema_model=ReloadEnvelope)
    except Exception as error:
        logger.exception("Error reloading configuration")
        return execution_error_response(error, request, "reload")


async def _cleanup_async_http_clients(_app: web.Application) -> None:
    """Best-effort shutdown for async HTTP clients used by provider SDKs."""
    try:
        import litellm
    except ImportError:
        return

    close_async_clients = getattr(litellm, "close_litellm_async_clients", None)
    if callable(close_async_clients):
        try:
            maybe_coro = close_async_clients()
            if asyncio.iscoroutine(maybe_coro):
                await maybe_coro
        except Exception as exc:
            logger.debug(f"LiteLLM async client cleanup failed: {exc}")


def create_app(
    *,
    api_token: Optional[str] = None,
    allowed_origins: Optional[Sequence[str]] = None,
) -> web.Application:
    """Create the aiohttp application."""
    active_token = get_or_create_token() if api_token is None else api_token.strip()
    if not active_token or any(character.isspace() for character in active_token):
        raise ValueError("API token must be non-empty and contain no whitespace")
    active_origins = tuple(get_allowed_origins() if allowed_origins is None else allowed_origins)
    app = web.Application(
        middlewares=[security_middleware(active_token, active_origins)],
        client_max_size=1024**2,
    )

    # Routes
    app.router.add_route("OPTIONS", "/{path:.*}", handle_options)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/", handle_health)
    app.router.add_post("/ask", handle_ask)
    app.router.add_post("/stream", handle_stream)
    app.router.add_post("/reload", handle_reload)

    # Session management endpoints
    app.router.add_get("/api/sessions", handle_list_sessions)
    app.router.add_get("/api/sessions/{id}", handle_get_session)
    app.router.add_delete("/api/sessions/{id}", handle_delete_session)
    app.on_cleanup.append(_cleanup_async_http_clients)

    return app


def run_server(host: str = "127.0.0.1", port: int = 8772) -> None:
    """Run the HTTP server."""
    app = create_app()
    transport = resolve_transport("MATILDA_BRAIN_TRANSPORT", "MATILDA_BRAIN_ENDPOINT", host, port)

    address = (
        transport.endpoint if transport.transport in {"unix", "pipe"} else f"http://{transport.host}:{transport.port}"
    )
    print(f"Starting Brain server on {address}")
    print()
    print("AI Endpoints:")
    print("  POST /ask    - One-shot AI request")
    print("  POST /stream - Streaming AI request (SSE)")
    print()
    print("Session Endpoints:")
    print("  GET    /api/sessions      - List all sessions")
    print("  GET    /api/sessions/{id} - Get session by ID")
    print("  DELETE /api/sessions/{id} - Delete session")
    print()
    print("Health:")
    print("  GET  /health - Health check")
    print()

    if transport.transport == "unix" and transport.endpoint:
        prepare_unix_socket(transport.endpoint)
        web.run_app(app, path=transport.endpoint, print=None)
        return
    if transport.transport == "pipe":
        ensure_pipe_supported(transport)
        pipe_endpoint = transport.endpoint
        assert pipe_endpoint is not None

        async def run_pipe() -> None:
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.NamedPipeSite(runner, pipe_endpoint)
            await site.start()
            await asyncio.Event().wait()

        asyncio.run(run_pipe())
        return

    web.run_app(app, host=transport.host, port=transport.port, print=None)


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Matilda Brain HTTP Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", "-p", type=int, default=8772, help="Port to listen on")
    args = parser.parse_args()

    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
