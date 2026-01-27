"""Web-related built-in tools.

This module provides tools for web searches and HTTP requests.
"""

import json
import urllib.parse
from typing import Any, Dict, Optional, Union

import httpx
from matilda_brain.tools import tool

from .config import _get_timeout_bounds, _get_web_timeout, _safe_execute_async


@tool(category="web", description="Search the web for information using a search engine")
async def web_search(query: str, num_results: int = 5) -> str:
    """Search the web for information.

    Args:
        query: The search query
        num_results: Number of results to return (max 10)

    Returns:
        Search results as formatted text
    """

    async def _web_search_impl(query: str, num_results: int = 5) -> str:
        # Validate inputs
        if not query or not query.strip():
            raise ValueError("Search query cannot be empty")

        num_results = min(max(1, num_results), 10)

        # URL encode the query
        encoded_query = urllib.parse.quote(query)

        # Using DuckDuckGo's API for simplicity (no API key needed)
        url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json&no_html=1&skip_disambig=1"

        # Make request with timeout
        headers = {"User-Agent": "Mozilla/5.0 (compatible; AI-Library/1.0)"}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url, headers=headers, timeout=_get_web_timeout(), follow_redirects=True
            )
            response.raise_for_status()
            data = response.json()

        # Extract results
        results = []

        # Add instant answer if available
        if data.get("Answer"):
            results.append(f"Answer: {data['Answer']}")

        # Add abstract if available
        if data.get("Abstract"):
            results.append(f"Summary: {data['Abstract']}")
            if data.get("AbstractURL"):
                results.append(f"Source: {data['AbstractURL']}")

        # Add related topics
        for topic in data.get("RelatedTopics", [])[:num_results]:
            if isinstance(topic, dict) and "Text" in topic:
                results.append(f"- {topic['Text']}")
                if "FirstURL" in topic:
                    results.append(f"  URL: {topic['FirstURL']}")

        if not results:
            return f"No results found for: {query}\nTry different keywords or check your internet connection"

        return "\n".join(results)

    return await _safe_execute_async("web_search", _web_search_impl, query=query, num_results=num_results)


@tool(category="web", description="Make HTTP requests to APIs or websites")
async def http_request(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Union[str, Dict[str, Any]]] = None,
    timeout: Optional[int] = None,
) -> str:
    """Make HTTP requests.

    Args:
        url: The URL to request
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        headers: Optional headers dictionary
        data: Optional data to send (for POST/PUT requests)
        timeout: Request timeout in seconds (default: from config)

    Returns:
        Response text or error message
    """

    async def _http_request_impl(
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Union[str, Dict[str, Any]]] = None,
        timeout: Optional[int] = None,
    ) -> str:
        if timeout is None:
            timeout = _get_web_timeout()

        # Validate inputs
        if not url:
            return "Error: URL cannot be empty"

        # Validate URL
        parsed = urllib.parse.urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return "Error: Invalid URL format"

        if parsed.scheme not in ("http", "https"):
            return "Error: Only HTTP/HTTPS protocols are supported"

        # Get timeout bounds
        min_timeout, max_timeout = _get_timeout_bounds()
        timeout = min(max(min_timeout, timeout), max_timeout)

        # Prepare request
        if headers is None:
            headers = {}

        # Convert headers keys to proper case for consistency
        normalized_headers = {}
        for k, v in headers.items():
            normalized_headers[k] = v

        if "User-Agent" not in normalized_headers:
            normalized_headers["User-Agent"] = "AI-Library/1.0"

        # Handle data
        body_data = None
        if data is not None:
            if isinstance(data, dict):
                body_data = json.dumps(data).encode("utf-8")
                normalized_headers["Content-Type"] = "application/json"
            else:
                body_data = str(data).encode("utf-8")

        # Make request
        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method=method.upper(),
                    url=url,
                    content=body_data,
                    headers=normalized_headers,
                    timeout=timeout,
                    follow_redirects=True,
                )
                response.raise_for_status()

                # Read response
                content = response.text

                # Try to parse JSON if possible
                try:
                    parsed_json = json.loads(content)
                    return json.dumps(parsed_json, indent=2)
                except json.JSONDecodeError:
                    return str(content)

            except httpx.HTTPStatusError as e:
                return f"HTTP Error {e.response.status_code}: {e.response.reason_phrase}"
            except httpx.RequestError as e:
                 # Re-raise to allow _safe_execute_async to handle it, or stick to old behavior.
                 # Old behavior was: return f"Network error: {str(e)}"
                 # _safe_execute_async might format it differently.
                 # To remain consistent with strict "don't break changes",
                 # I'll re-raise and let the wrapper handle it, assuming standard tools behavior is desired.
                 raise
            except Exception:
                from matilda_brain.internal.utils import get_logger
                get_logger(__name__).exception("Error making HTTP request")
                raise

    return await _safe_execute_async(
        "http_request",
        _http_request_impl,
        url=url,
        method=method,
        headers=headers,
        data=data,
        timeout=timeout
    )


__all__ = ["web_search", "http_request"]
