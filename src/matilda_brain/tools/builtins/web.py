"""Web-related built-in tools.

This module provides tools for web searches and HTTP requests.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Union

from matilda_brain.tools import tool

from .config import _get_timeout_bounds, _get_web_timeout, _safe_execute


@tool(category="web", description="Search the web for information using a search engine")
def web_search(query: str, num_results: int = 5) -> str:
    """Search the web for information.

    Args:
        query: The search query
        num_results: Number of results to return (max 10)

    Returns:
        Search results as formatted text
    """

    def _web_search_impl(query: str, num_results: int = 5) -> str:
        # Validate inputs
        if not query or not query.strip():
            raise ValueError("Search query cannot be empty")

        num_results = min(max(1, num_results), 10)

        # URL encode the query
        encoded_query = urllib.parse.quote(query)

        # Using DuckDuckGo's API for simplicity (no API key needed)
        url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json&no_html=1&skip_disambig=1"

        # Make request with timeout
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; AI-Library/1.0)"})

        with urllib.request.urlopen(req, timeout=_get_web_timeout()) as response:
            data = json.loads(response.read().decode("utf-8"))

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

    return _safe_execute("web_search", _web_search_impl, query=query, num_results=num_results)


@tool(category="web", description="Make HTTP requests to APIs or websites")
def http_request(
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
    if timeout is None:
        timeout = _get_web_timeout()

    try:
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

        # Create request
        req = urllib.request.Request(url, data=body_data, headers=normalized_headers, method=method.upper())

        # Make request
        with urllib.request.urlopen(req, timeout=timeout) as response:
            # Read response
            content = response.read().decode("utf-8", errors="replace")

            # Try to parse JSON if possible
            try:
                parsed_json = json.loads(content)
                return json.dumps(parsed_json, indent=2)
            except json.JSONDecodeError:
                return str(content)

    except urllib.error.HTTPError as e:
        try:
            e.close()
        except Exception:
            pass
        return f"HTTP Error {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return f"Network error: {str(e)}"
    except Exception:
        from matilda_brain.internal.utils import get_logger

        get_logger(__name__).exception("Error making HTTP request")
        return "Error making request - see logs for details"


__all__ = ["web_search", "http_request"]
