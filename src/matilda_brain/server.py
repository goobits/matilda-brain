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
import json
import os
import secrets
from typing import Optional

from aiohttp import web
from aiohttp.web import Request, Response, StreamResponse

from .core.api import ask_async, stream_async
from .session.manager import ChatSessionManager
from .utils import get_logger

logger = get_logger(__name__)

# Shared session manager instance
_session_manager: Optional[ChatSessionManager] = None

# Security: API Token Management
API_TOKEN = os.getenv("MATILDA_API_TOKEN")
if not API_TOKEN:
    API_TOKEN = secrets.token_hex(32)
    print("⚠️  SECURITY WARNING: MATILDA_API_TOKEN not set.")
    print(f"⚠️  Generated temporary secure token: {API_TOKEN}")
    print("⚠️  Please set MATILDA_API_TOKEN in your environment for persistence.")

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
        return add_cors_headers(web.json_response(
            {"error": "Unauthorized: Missing or invalid Authorization header"}, 
            status=401
        ), request)
    
    token = auth_header.split(" ")[1]
    if not secrets.compare_digest(token, API_TOKEN):
        return add_cors_headers(web.json_response(
            {"error": "Forbidden: Invalid token"}, 
            status=403
        ), request)

    return await handler(request)

def get_session_manager() -> ChatSessionManager:
    """Get or create the session manager singleton."""
    global _session_manager
    if _session_manager is None:
        _session_manager = ChatSessionManager()
    return _session_manager


# CORS headers for browser access
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")

def add_cors_headers(response: Response, request: Request = None) -> Response:
    """Add CORS headers to response."""
    origin = "*"
    if request:
        req_origin = request.headers.get("Origin")
        if req_origin in ALLOWED_ORIGINS:
            origin = req_origin
        else:
            origin = ALLOWED_ORIGINS[0]
            
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
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

    try:
        # Build messages list for the API
        all_messages = []

        # Add system prompt if provided
        if system:
            all_messages.append({"role": "system", "content": system})

        # Add conversation history
        if messages:
            all_messages.extend(messages)

        # Add current prompt
        all_messages.append({"role": "user", "content": prompt})

        # Make the request with full message history
        response = await ask_async(
            prompt,
            model=model,
            system=system if not messages else None,  # Only use system if no history
            temperature=temperature,
            max_tokens=max_tokens,
            messages=all_messages if messages else None,  # Pass messages to backend
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
    # Calculate CORS origin
    req_origin = request.headers.get("Origin")
    if req_origin in ALLOWED_ORIGINS:
        origin = req_origin
    else:
        origin = ALLOWED_ORIGINS[0]

    try:
        data = await request.json()
    except json.JSONDecodeError:
        return add_cors_headers(web.json_response({"error": "Invalid JSON"}, status=400), request)

    prompt = data.get("prompt")
    if not prompt:
        return add_cors_headers(web.json_response({"error": "Missing 'prompt' field"}, status=400), request)

    response = StreamResponse(
        status=200,
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        },
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
            return add_cors_headers(web.json_response({"error": f"Session '{session_id}' not found"}, status=404), request)

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
            return add_cors_headers(web.json_response({"error": f"Session '{session_id}' not found"}, status=404), request)
    except Exception as e:
        logger.exception(f"Error deleting session {session_id}")
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

    # Session management endpoints
    app.router.add_get("/api/sessions", handle_list_sessions)
    app.router.add_get("/api/sessions/{id}", handle_get_session)
    app.router.add_delete("/api/sessions/{id}", handle_delete_session)

    return app


def run_server(host: str = "0.0.0.0", port: int = 8772):
    """Run the HTTP server."""
    app = create_app()

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

    web.run_app(app, host=host, port=port, print=None)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="TTT HTTP Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", "-p", type=int, default=8772, help="Port to listen on")
    args = parser.parse_args()

    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
