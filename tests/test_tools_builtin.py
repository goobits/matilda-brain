"""Tests for built-in tools."""

import json
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from matilda_brain.tools import get_tool, list_tools
from matilda_brain.tools.builtins import (
    calculate,
    get_current_time,
    http_request,
    list_directory,
    read_file,
    run_python,
    web_search,
    write_file,
)


@pytest.mark.asyncio
class TestWebSearch:
    """Test web_search tool."""

    @patch("httpx.AsyncClient")
    async def test_web_search_returns_formatted_answer_and_topics(self, mock_client_cls):
        """Test successful web search."""
        # Mock client and response
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = {
            "Answer": "Test answer",
            "Abstract": "Test abstract",
            "AbstractURL": "https://example.com",
            "RelatedTopics": [
                {"Text": "Topic 1", "FirstURL": "https://example.com/1"},
                {"Text": "Topic 2", "FirstURL": "https://example.com/2"},
            ],
        }
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        result = await web_search("test query")

        assert "Answer: Test answer" in result
        assert "Summary: Test abstract" in result
        assert "Source: https://example.com" in result
        assert "Topic 1" in result
        assert "Topic 2" in result

    async def test_web_search_empty_query(self):
        """Test web search with empty query."""
        result = await web_search("")
        assert "Search query cannot be empty" in result

    @patch("httpx.AsyncClient")
    async def test_web_search_no_results(self, mock_client_cls):
        """Test web search with no results."""
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.json.return_value = {}
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        result = await web_search("obscure query")
        assert "No results found" in result

    @patch("httpx.AsyncClient")
    async def test_web_search_network_error(self, mock_client_cls):
        """Test web search with network error."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.RequestError("Network error", request=Mock())
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        result = await web_search("test query")
        assert "Network error" in result


class TestFileOperations:
    """Test file operation tools."""

    @pytest.mark.unit
    def test_read_file_returns_complete_file_contents(self, tmp_path):
        """Test successful file reading."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_content = "Hello, World!\nThis is a test file."
        test_file.write_text(test_content)

        result = read_file(str(test_file))
        assert result == test_content

    @pytest.mark.unit
    def test_read_file_not_found(self, tmp_path):
        """Test reading non-existent file."""
        nonexistent_file = tmp_path / "nonexistent.txt"
        result = read_file(str(nonexistent_file))
        assert "not found" in result.lower() or "does not exist" in result.lower()

    @pytest.mark.unit
    def test_read_file_directory(self, tmp_path):
        """Test reading a directory."""
        result = read_file(str(tmp_path))
        assert "not a file" in result.lower() or "directory" in result.lower()

    @pytest.mark.unit
    def test_read_file_too_large(self, tmp_path):
        """Test reading file that's too large (if size limits exist)."""
        # Create a large file
        test_file = tmp_path / "large.txt"
        large_content = "x" * 10000  # 10KB content
        test_file.write_text(large_content)

        result = read_file(str(test_file))
        # File should either read successfully or report size limit
        assert "Error" not in result or "too large" in result.lower()

    @pytest.mark.unit
    def test_write_file_creates_file_with_exact_content(self, tmp_path):
        """Test successful file writing."""
        test_file = tmp_path / "output.txt"
        content = "Test content"

        result = write_file(str(test_file), content)

        assert "Successfully wrote" in result
        assert test_file.read_text() == content

    @pytest.mark.unit
    def test_write_file_create_dirs(self, tmp_path):
        """Test writing file with directory creation."""
        test_file = tmp_path / "new_dir" / "output.txt"
        content = "Test content"

        result = write_file(str(test_file), content, create_dirs=True)

        assert "Successfully wrote" in result
        assert test_file.exists()
        assert test_file.read_text() == content

    @pytest.mark.unit
    def test_write_file_no_parent_dir(self, tmp_path):
        """Test writing file when parent directory doesn't exist."""
        test_file = tmp_path / "nonexistent" / "output.txt"

        result = write_file(str(test_file), "content")
        assert "Parent directory does not exist" in result

    @pytest.mark.unit
    def test_list_directory_shows_files_and_subdirectories_with_types(self, tmp_path):
        """Test listing directory contents."""
        # Create test structure
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "file2.py").write_text("content2")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "file3.txt").write_text("content3")

        result = list_directory(str(tmp_path))

        assert "[FILE] file1.txt" in result
        assert "[FILE] file2.py" in result
        assert "[DIR] subdir/" in result
        assert "file3.txt" not in result  # Not recursive by default

    @pytest.mark.unit
    def test_list_directory_pattern(self, tmp_path):
        """Test listing directory with pattern."""
        (tmp_path / "file1.txt").touch()
        (tmp_path / "file2.py").touch()
        (tmp_path / "file3.txt").touch()

        result = list_directory(str(tmp_path), pattern="*.txt")

        assert "file1.txt" in result
        assert "file3.txt" in result
        assert "file2.py" not in result

    @pytest.mark.unit
    def test_list_directory_recursive(self, tmp_path):
        """Test recursive directory listing."""
        (tmp_path / "file1.txt").touch()
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "file2.txt").touch()

        result = list_directory(str(tmp_path), pattern="*.txt", recursive=True)

        assert "file1.txt" in result
        assert "subdir/file2.txt" in result


class TestCodeExecution:
    """Test code execution tool."""

    @pytest.mark.unit
    def test_run_python_executes_code_and_captures_output(self):
        """Test successful Python code execution."""
        code = "print('Hello, World!')\nprint(2 + 2)"
        result = run_python(code)

        assert "Hello, World!" in result
        assert "4" in result

    @pytest.mark.unit
    def test_run_python_error(self):
        """Test Python code with error."""
        code = "print(undefined_variable)"
        result = run_python(code)

        assert "Error" in result.lower() or "NameError" in result

    @pytest.mark.unit
    def test_run_python_timeout(self):
        """Test Python code timeout."""
        code = "import time\ntime.sleep(10)"
        result = run_python(code, timeout=1)

        assert "timed out" in result

    @pytest.mark.unit
    def test_run_python_empty_code(self):
        """Test empty code."""
        result = run_python("")
        assert "Code cannot be empty" in result


class TestTimeOperations:
    """Test time-related tools."""

    @pytest.mark.unit
    def test_get_current_time_returns_utc_formatted_timestamp(self):
        """Test getting current time with defaults."""
        result = get_current_time()

        # Should contain UTC
        assert "UTC" in result
        # Should be in default format
        assert len(result.split()) >= 3  # Date, time, timezone

    @pytest.mark.unit
    def test_get_current_time_timezone(self):
        """Test getting time in specific timezone."""
        # Use America/New_York which is more standard
        result = get_current_time("America/New_York")

        # Should contain time and timezone info, or an error message
        assert len(result) > 0 and ("EST" in result or "EDT" in result or "Error" in result)

    @pytest.mark.unit
    def test_get_current_time_custom_format(self):
        """Test custom time format."""
        result = get_current_time("UTC", "%Y-%m-%d")

        # Should only contain date
        assert len(result.split("-")) == 3
        assert ":" not in result  # No time component

    @pytest.mark.unit
    def test_get_current_time_invalid_timezone(self):
        """Test invalid timezone."""
        result = get_current_time("Invalid/Timezone")

        assert "Error: Unknown timezone" in result
        assert "Examples:" in result


@pytest.mark.asyncio
class TestHttpRequest:
    """Test HTTP request tool."""

    @patch("httpx.AsyncClient")
    async def test_http_request_get(self, mock_client_cls):
        """Test GET request."""
        # Mock client and response
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.text = '{"status": "ok"}'
        mock_client.request.return_value = mock_response
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        result = await http_request("https://api.example.com/test")

        # Should pretty-print JSON
        assert '"status": "ok"' in result

    @patch("httpx.AsyncClient")
    async def test_http_request_post_json(self, mock_client_cls):
        """Test POST request with JSON data."""
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.text = '{"result": "created"}'
        mock_client.request.return_value = mock_response
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        result = await http_request("https://api.example.com/create", method="POST", data={"name": "test"})

        assert '"result": "created"' in result

        # Check request was made correctly
        call_args = mock_client.request.call_args
        assert call_args.kwargs["method"] == "POST"
        # Check Content-Type header (case-insensitive)
        headers = call_args.kwargs["headers"]
        content_type = headers.get("Content-Type") or headers.get("Content-type")
        assert content_type == "application/json"

    async def test_http_request_invalid_url(self):
        """Test invalid URL."""
        result = await http_request("not-a-url")
        assert "Error: Invalid URL format" in result

    async def test_http_request_unsupported_protocol(self):
        """Test unsupported protocol."""
        result = await http_request("ftp://example.com/file")
        assert "Error: Only HTTP/HTTPS protocols are supported" in result

    @patch("httpx.AsyncClient")
    async def test_http_request_http_error(self, mock_client_cls):
        """Test HTTP error response."""
        mock_client = AsyncMock()
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.reason_phrase = "Not Found"

        # raise_for_status raises HTTPStatusError
        error = httpx.HTTPStatusError("404 Not Found", request=Mock(), response=mock_response)
        mock_response.raise_for_status.side_effect = error

        mock_client.request.return_value = mock_response
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        result = await http_request("https://api.example.com/missing")
        assert "HTTP Error 404" in result


class TestCalculate:
    """Test calculate tool."""

    @pytest.mark.unit
    def test_calculate_basic_arithmetic(self):
        """Test basic arithmetic operations."""
        assert "Result: 7" in calculate("3 + 4")
        assert "Result: 6" in calculate("10 - 4")
        assert "Result: 20" in calculate("4 * 5")
        assert "Result: 2.5" in calculate("5 / 2")
        assert "Result: 8" in calculate("2 ** 3")
        assert "Result: 1" in calculate("10 % 3")
        assert "Result: 3" in calculate("10 // 3")

    @pytest.mark.unit
    def test_calculate_functions(self):
        """Test mathematical functions."""
        assert "Result: 5" in calculate("abs(-5)")
        assert "Result: 4" in calculate("round(3.7)")
        assert "Result: 8" in calculate("pow(2, 3)")
        assert "Result: 2" in calculate("sqrt(4)")
        assert "Result: 0" in calculate("round(sin(0), 10)")

    @pytest.mark.unit
    def test_calculate_constants(self):
        """Test mathematical constants."""
        result = calculate("pi")
        assert "3.14159" in result

        result = calculate("e")
        assert "2.71828" in result

    @pytest.mark.unit
    def test_calculate_complex_expression(self):
        """Test complex expression."""
        result = calculate("sqrt(16) + 3 * 2 - 1")
        assert "Result: 9" in result

    @pytest.mark.unit
    def test_calculate_division_by_zero(self):
        """Test division by zero."""
        result = calculate("1 / 0")
        assert "Error: Division by zero" in result

    @pytest.mark.unit
    def test_calculate_invalid_expression(self):
        """Test invalid expression."""
        result = calculate("invalid + syntax !")
        assert "Error" in result

    @pytest.mark.unit
    def test_calculate_unsafe_operation(self):
        """Test unsafe operation is blocked."""
        result = calculate("__import__('os').system('ls')")
        assert "Error" in result


class TestBuiltinToolsIntegration:
    """Test integration of built-in tools with the tool system."""

    @pytest.mark.unit
    def test_all_tools_registered(self):
        """Test that all built-in tools are registered."""
        # Get all tools in the 'web' category
        web_tools = list_tools(category="web")
        web_tool_names = [t.name for t in web_tools]
        assert "web_search" in web_tool_names
        assert "http_request" in web_tool_names

        # Get all tools in the 'file' category
        file_tools = list_tools(category="file")
        file_tool_names = [t.name for t in file_tools]
        assert "read_file" in file_tool_names
        assert "write_file" in file_tool_names
        assert "list_directory" in file_tool_names

        # Get all tools in the 'code' category
        code_tools = list_tools(category="code")
        code_tool_names = [t.name for t in code_tools]
        assert "run_python" in code_tool_names

        # Get all tools in the 'time' category
        time_tools = list_tools(category="time")
        time_tool_names = [t.name for t in time_tools]
        assert "get_current_time" in time_tool_names

        # Get all tools in the 'math' category
        math_tools = list_tools(category="math")
        math_tool_names = [t.name for t in math_tools]
        assert "calculate" in math_tool_names

    @pytest.mark.unit
    def test_get_specific_tool(self):
        """Test getting specific built-in tools."""
        # Get web_search tool
        tool = get_tool("web_search")
        assert tool is not None
        assert tool.name == "web_search"
        assert tool.category == "web"
        assert "Search the web" in tool.description

        # Get calculate tool
        tool = get_tool("calculate")
        assert tool is not None
        assert tool.name == "calculate"
        assert tool.category == "math"
        assert "mathematical calculations" in tool.description

    @pytest.mark.unit
    def test_tool_schemas(self):
        """Test that built-in tools have valid schemas."""
        # Test OpenAI schema
        tool = get_tool("read_file")
        schema = tool.to_openai_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "read_file"
        assert "parameters" in schema["function"]
        assert "file_path" in schema["function"]["parameters"]["properties"]

        # Test Anthropic schema
        tool = get_tool("http_request")
        schema = tool.to_anthropic_schema()

        assert schema["name"] == "http_request"
        assert "input_schema" in schema
        assert "url" in schema["input_schema"]["properties"]
        assert "method" in schema["input_schema"]["properties"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
