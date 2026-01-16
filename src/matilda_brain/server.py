"""
Simple HTTP server for TTT (Text-to-Text) API.

Exposes TTT functionality over HTTP for browser-based clients.
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
from datetime import datetime
from typing import Optional

from aiohttp import web
from aiohttp.web import Request, Response, StreamResponse

from .core.api import stream_async
from .internal.security import get_allowed_origins, is_origin_allowed
from .session.manager import ChatSessionManager
from .session.chat import PersistentChatSession
from .internal.token_storage import get_or_create_token
from .internal.utils import get_logger
from matilda_transport import ensure_pipe_supported, prepare_unix_socket, resolve_transport

logger = get_logger(__name__)

# Shared session manager instance
_session_manager: Optional[ChatSessionManager] = None

# Security: API Token Management
API_TOKEN = get_or_create_token()


@web.middleware
async def auth_middleware(request: Request, handler):
    """Middleware to enforce token authentication."""
    # Allow public endpoints
    if request.path in ["/", "/health"]:
        return await handler(request)

    # Allow CORS preflight options
    if request.method == "OPTIONS":
        return await handler(request)

    # Check Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return add_cors_headers(
            web.json_response({"error": "Unauthorized: Missing or invalid Authorization header"}, status=401), request
        )

    token = auth_header.split(" ")[1]
    if not secrets.compare_digest(token, API_TOKEN):
        return add_cors_headers(web.json_response({"error": "Forbidden: Invalid token"}, status=403), request)

    return await handler(request)


def get_session_manager() -> ChatSessionManager:
    """Get or create the session manager singleton."""
    global _session_manager
    if _session_manager is None:
        _session_manager = ChatSessionManager()
    return _session_manager


# CORS headers for browser access
# Uses secure defaults from security module
ALLOWED_ORIGINS = get_allowed_origins()


def add_cors_headers(response: Response, request: Request = None) -> Response:
    """
    Add CORS headers to response.

    Only sets Access-Control-Allow-Origin when:
    - A request with Origin header is provided, AND
    - That origin is in the allowed origins list

    If no origin is allowed, CORS headers are not set (browser will block the request).
    """
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"

    if request:
        req_origin = request.headers.get("Origin")
        if req_origin and is_origin_allowed(req_origin, ALLOWED_ORIGINS):
            response.headers["Access-Control-Allow-Origin"] = req_origin
        # If origin not allowed, don't set Access-Control-Allow-Origin header
        # This causes the browser to block the request (secure default)

    return response


async def handle_options(request: Request) -> Response:
    """Handle CORS preflight requests."""
    return add_cors_headers(Response(status=200), request)


async def handle_health(request: Request) -> Response:
    """Health check endpoint."""
    return add_cors_headers(web.json_response({"status": "ok", "service": "brain"}), request)


async def handle_ask(request: Request) -> Response:
    """
    Handle AI request with optional conversation history.

    POST /ask
    {
        "prompt": "What is Python?",
        "model": "gpt-4",           // optional
        "system": "Be concise",     // optional
        "temperature": 0.7,         // optional
        "max_tokens": 2048,         // optional
        "messages": [               // optional - conversation history
            {"role": "user", "content": "My favorite color is purple"},
            {"role": "assistant", "content": "Nice! Purple is a great color."}
        ]
    }

    Response:
    {
        "text": "Python is a programming language...",
        "model": "gpt-4",
        "tokens": {"prompt": 10, "completion": 50}
    }
    """
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return add_cors_headers(web.json_response({"error": "Invalid JSON"}, status=400), request)

    prompt = data.get("prompt")
    if not prompt:
        return add_cors_headers(web.json_response({"error": "Missing 'prompt' field"}, status=400), request)

    messages = data.get("messages", [])
    model = data.get("model")
    system = data.get("system")
    temperature = data.get("temperature")
    max_tokens = data.get("max_tokens")
    agent_name = request.headers.get("X-Agent-Name") or data.get("agent_name") or "assistant"
    memory_enabled = data.get("memory_enabled", True)

    try:
        if system is None and messages:
            for msg in messages:
                if msg.get("role") == "system" and isinstance(msg.get("content"), str):
                    system = msg["content"]
                    break

        history_messages = []
        if messages:
            timestamp = datetime.utcnow().isoformat()
            for msg in messages:
                if msg.get("role") == "system":
                    continue
                history_messages.append(
                    {"role": msg.get("role"), "content": msg.get("content"), "timestamp": timestamp}
                )

        session = PersistentChatSession(
            system=system,
            model=model,
            agent_name=agent_name,
            memory_enabled=memory_enabled,
        )
        if history_messages:
            session.history = history_messages

        response = session.ask(
            prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        result = {
            "text": str(response),
            "model": getattr(response, "model", None),
        }

        # Add token usage if available
        if hasattr(response, "usage") and response.usage:
            result["tokens"] = {
                "prompt": getattr(response.usage, "prompt_tokens", 0),
                "completion": getattr(response.usage, "completion_tokens", 0),
            }

        return add_cors_headers(web.json_response(result), request)

    except Exception as e:
        logger.exception("Error processing request")
        return add_cors_headers(web.json_response({"error": str(e)}, status=500), request)


async def handle_stream(request: Request) -> StreamResponse:
    """
    Handle streaming AI request.

    POST /stream
    {
        "prompt": "Tell me a story",
        "model": "gpt-4",           // optional
        "system": "Be creative",    // optional
        "temperature": 0.9          // optional
    }

    Response: Server-Sent Events (SSE)
    data: {"chunk": "Once"}
    data: {"chunk": " upon"}
    data: {"chunk": " a time..."}
    data: {"done": true}
    """
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return add_cors_headers(web.json_response({"error": "Invalid JSON"}, status=400), request)

    prompt = data.get("prompt")
    if not prompt:
        return add_cors_headers(web.json_response({"error": "Missing 'prompt' field"}, status=400), request)

    # Build CORS headers safely - only include Access-Control-Allow-Origin if origin is allowed
    stream_headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
    }

    # Only add Access-Control-Allow-Origin if the request origin is allowed
    req_origin = request.headers.get("Origin")
    if req_origin and is_origin_allowed(req_origin, ALLOWED_ORIGINS):
        stream_headers["Access-Control-Allow-Origin"] = req_origin

    response = StreamResponse(
        status=200,
        headers=stream_headers,
    )
    await response.prepare(request)

    try:
        async for chunk in stream_async(
            prompt,
            model=data.get("model"),
            system=data.get("system"),
            temperature=data.get("temperature"),
            max_tokens=data.get("max_tokens"),
        ):
            event_data = json.dumps({"chunk": chunk})
            await response.write(f"data: {event_data}\n\n".encode())

        # Send done event
        await response.write(b'data: {"done": true}\n\n')

    except Exception as e:
        logger.exception("Error during streaming")
        error_data = json.dumps({"error": str(e)})
        await response.write(f"data: {error_data}\n\n".encode())

    await response.write_eof()
    return response


async def handle_list_sessions(request: Request) -> Response:
    """
    List all chat sessions.

    GET /api/sessions

    Response:
    [
        {
            "id": "20250101_120000_abc12345",
            "created_at": "2025-01-01T12:00:00",
            "updated_at": "2025-01-01T12:05:00",
            "message_count": 5,
            "last_message": "What is Python?...",
            "model": "gpt-4"
        }
    ]
    """
    try:
        manager = get_session_manager()
        sessions = manager.list_sessions()
        return add_cors_headers(web.json_response(sessions), request)
    except Exception as e:
        logger.exception("Error listing sessions")
        return add_cors_headers(web.json_response({"error": str(e)}, status=500), request)


async def handle_get_session(request: Request) -> Response:
    """
    Get a specific session by ID.

    GET /api/sessions/{id}

    Response:
    {
        "id": "20250101_120000_abc12345",
        "created_at": "2025-01-01T12:00:00",
        "updated_at": "2025-01-01T12:05:00",
        "messages": [...],
        "model": "gpt-4"
    }
    """
    session_id = request.match_info.get("id")
    if not session_id:
        return add_cors_headers(web.json_response({"error": "Missing session ID"}, status=400), request)

    try:
        manager = get_session_manager()
        session = manager.load_session(session_id)

        if session is None:
            return add_cors_headers(
                web.json_response({"error": f"Session '{session_id}' not found"}, status=404), request
            )

        return add_cors_headers(web.json_response(session.to_dict()), request)
    except Exception as e:
        logger.exception(f"Error loading session {session_id}")
        return add_cors_headers(web.json_response({"error": str(e)}, status=500), request)


async def handle_delete_session(request: Request) -> Response:
    """
    Delete a session by ID.

    DELETE /api/sessions/{id}

    Response:
    {"status": "deleted", "id": "session_id"}
    """
    session_id = request.match_info.get("id")
    if not session_id:
        return add_cors_headers(web.json_response({"error": "Missing session ID"}, status=400), request)

    try:
        manager = get_session_manager()
        deleted = manager.delete_session(session_id)

        if deleted:
            return add_cors_headers(web.json_response({"status": "deleted", "id": session_id}), request)
        else:
            return add_cors_headers(
                web.json_response({"error": f"Session '{session_id}' not found"}, status=404), request
            )
    except Exception as e:
        logger.exception(f"Error deleting session {session_id}")
        return add_cors_headers(web.json_response({"error": str(e)}, status=500), request)


async def handle_reload(request: Request) -> Response:
    """
    Reload configuration from disk.

    POST /reload

    Response:
    {"status": "ok", "message": "Configuration reloaded"}
    """
    try:
        from .config.schema import load_config, set_config

        # Reload configuration from file
        new_config = load_config()
        # Update global config state
        set_config(new_config)

        logger.info("Configuration reloaded via API")
        return add_cors_headers(web.json_response({"status": "ok", "message": "Configuration reloaded"}), request)
    except Exception as e:
        logger.exception("Error reloading configuration")
        return add_cors_headers(web.json_response({"error": str(e)}, status=500), request)


def create_app() -> web.Application:
    """Create the aiohttp application."""
    app = web.Application(middlewares=[auth_middleware])

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

    return app


def run_server(host: str = "0.0.0.0", port: int = 8772):
    """Run the HTTP server."""
    app = create_app()
    transport = resolve_transport("MATILDA_BRAIN_TRANSPORT", "MATILDA_BRAIN_ENDPOINT", host, port)

    print(f"Starting Brain server on http://{host}:{port}")
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
        async def run_pipe():
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.NamedPipeSite(runner, transport.endpoint)
            await site.start()
            await asyncio.Event().wait()

        asyncio.run(run_pipe())
        return

    web.run_app(app, host=transport.host, port=transport.port, print=None)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="TTT HTTP Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", "-p", type=int, default=8772, help="Port to listen on")
    args = parser.parse_args()

    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
