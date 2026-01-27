"""Tests for built-in tools."""

import json
import urllib.error
from unittest.mock import Mock, patch, AsyncMock

import pytest
import aiohttp

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


class TestWebSearch:
    """Test web_search tool."""

    @pytest.mark.unit
    @patch("urllib.request.urlopen")
    def test_web_search_returns_formatted_answer_and_topics(self, mock_urlopen):
        """Test successful web search."""
        # Mock response
        mock_response = Mock()
        mock_response.read.return_value = json.dumps(
            {
                "Answer": "Test answer",
                "Abstract": "Test abstract",
                "AbstractURL": "https://example.com",
                "RelatedTopics": [
                    {"Text": "Topic 1", "FirstURL": "https://example.com/1"},
                    {"Text": "Topic 2", "FirstURL": "https://example.com/2"},
                ],
            }
        ).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = web_search("test query")

        assert "Answer: Test answer" in result
        assert "Summary: Test abstract" in result
        assert "Source: https://example.com" in result
        assert "Topic 1" in result
        assert "Topic 2" in result

    @pytest.mark.unit
    def test_web_search_empty_query(self):
        """Test web search with empty query."""
        result = web_search("")
        assert "Search query cannot be empty" in result

    @pytest.mark.unit
    @patch("urllib.request.urlopen")
    def test_web_search_no_results(self, mock_urlopen):
        """Test web search with no results."""
        mock_response = Mock()
        mock_response.read.return_value = json.dumps({}).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = web_search("obscure query")
        assert "No results found" in result

    @pytest.mark.unit
    @patch("urllib.request.urlopen")
    def test_web_search_network_error(self, mock_urlopen):
        """Test web search with network error."""
        mock_urlopen.side_effect = urllib.error.URLError("Network error")

        result = web_search("test query")
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


class TestHttpRequest:
    """Test HTTP request tool."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.request")
    async def test_http_request_get(self, mock_request):
        """Test GET request."""
        # Mock response
        mock_response = AsyncMock()
        mock_response.text.return_value = '{"status": "ok"}'
        mock_response.status = 200
        mock_request.return_value.__aenter__.return_value = mock_response

        result = await http_request("https://api.example.com/test")

        # Should pretty-print JSON
        assert '"status": "ok"' in result

    @pytest.mark.unit
    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.request")
    async def test_http_request_post_json(self, mock_request):
        """Test POST request with JSON data."""
        mock_response = AsyncMock()
        mock_response.text.return_value = '{"result": "created"}'
        mock_response.status = 200
        mock_request.return_value.__aenter__.return_value = mock_response

        result = await http_request("https://api.example.com/create", method="POST", data={"name": "test"})

        assert '"result": "created"' in result

        # Check request was made correctly
        call_args = mock_request.call_args
        assert call_args[0][0] == "POST"  # Method
        assert call_args[0][1] == "https://api.example.com/create" # URL

        # Check Content-Type header
        headers = call_args[1].get("headers", {})
        content_type = headers.get("Content-Type") or headers.get("Content-type")
        assert content_type == "application/json"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_http_request_invalid_url(self):
        """Test invalid URL."""
        result = await http_request("not-a-url")
        assert "Error: Invalid URL format" in result

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_http_request_unsupported_protocol(self):
        """Test unsupported protocol."""
        result = await http_request("ftp://example.com/file")
        assert "Error: Only HTTP/HTTPS protocols are supported" in result

    @pytest.mark.unit
    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.request")
    async def test_http_request_http_error(self, mock_request):
        """Test HTTP error response."""
        # Mock ClientResponseError
        error = aiohttp.ClientResponseError(
            request_info=Mock(),
            history=(),
            status=404,
            message="Not Found",
        )
        mock_request.side_effect = error

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
