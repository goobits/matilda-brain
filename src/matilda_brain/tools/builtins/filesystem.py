"""Filesystem-related built-in tools.

This module provides tools for reading, writing, and listing files.
"""

from pathlib import Path
from typing import Optional

from matilda_brain.tools import tool

from .config import _get_max_file_size, _safe_execute


@tool(category="file", description="Read the contents of a file")
def read_file(file_path: str, encoding: str = "utf-8") -> str:
    """Read contents of a file.

    Args:
        file_path: Path to the file to read
        encoding: File encoding (default: utf-8)

    Returns:
        File contents or error message
    """

    def _read_file_impl(file_path: str, encoding: str = "utf-8") -> str:
        # Validate file path
        path = Path(file_path).resolve()

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if not path.is_file():
            raise ValueError(f"Not a file: {file_path}")

        # Check file size
        file_size = path.stat().st_size
        max_file_size = _get_max_file_size()
        if file_size > max_file_size:
            raise ValueError(f"File too large ({file_size} bytes). Maximum size is {max_file_size} bytes.")

        # Read file
        with open(path, encoding=encoding) as f:
            content = f.read()

        return content

    return _safe_execute("read_file", _read_file_impl, file_path=file_path, encoding=encoding)


@tool(category="file", description="Write content to a file")
def write_file(file_path: str, content: str, encoding: str = "utf-8", create_dirs: bool = False) -> str:
    """Write content to a file.

    Args:
        file_path: Path to the file to write
        content: Content to write to the file
        encoding: File encoding (default: utf-8)
        create_dirs: Whether to create parent directories if they don't exist

    Returns:
        Success message or error
    """

    def _write_file_impl(file_path: str, content: str, encoding: str = "utf-8", create_dirs: bool = False) -> str:
        # Validate inputs
        if not file_path:
            raise ValueError("File path cannot be empty")

        path = Path(file_path).resolve()

        # Create parent directories if requested
        if create_dirs:
            path.parent.mkdir(parents=True, exist_ok=True)
        elif not path.parent.exists():
            raise FileNotFoundError(f"Parent directory does not exist: {path.parent}")

        # Write file
        with open(path, "w", encoding=encoding) as f:
            f.write(content)

        return f"Successfully wrote {len(content)} characters to {file_path}"

    return _safe_execute(
        "write_file",
        _write_file_impl,
        file_path=file_path,
        content=content,
        encoding=encoding,
        create_dirs=create_dirs,
    )


@tool(category="file", description="List files and directories in a given path")
def list_directory(
    path: str = ".",
    pattern: Optional[str] = None,
    recursive: bool = False,
    include_hidden: bool = False,
) -> str:
    """List files in a directory.

    Args:
        path: Directory path to list (default: current directory)
        pattern: Optional glob pattern to filter files (e.g., '*.py')
        recursive: Whether to search recursively
        include_hidden: Whether to include hidden files (starting with .)

    Returns:
        List of files and directories or error message
    """
    try:
        # Resolve path
        dir_path = Path(path).resolve()

        if not dir_path.exists():
            return f"Error: Directory not found: {path}"

        if not dir_path.is_dir():
            return f"Error: Not a directory: {path}"

        # List files
        results = []

        if recursive and pattern:
            # Use rglob for recursive pattern matching
            items = dir_path.rglob(pattern)
        elif pattern:
            # Use glob for pattern matching
            items = dir_path.glob(pattern)
        else:
            # List all items
            items = dir_path.iterdir()

        # Get size format thresholds from config
        try:
            from matilda_brain.config.schema import get_config

            config = get_config()
            size_config = config.model_dump().get("files", {}).get("size_format", {})
            kb_threshold = size_config.get("kb_threshold", 1024)
            mb_threshold = size_config.get("mb_threshold", 1048576)
        except (AttributeError, KeyError, ValueError, TypeError, ImportError):
            # Fallback to constants values
            kb_threshold = 1024
            mb_threshold = 1048576

        # Process items
        for item in sorted(items):
            # Skip hidden files if requested
            if not include_hidden and item.name.startswith("."):
                continue

            # Format item
            relative = item.relative_to(dir_path)
            if item.is_dir():
                results.append(f"[DIR] {relative}/")
            else:
                size = item.stat().st_size

                if size < kb_threshold:
                    size_str = f"{size}B"
                elif size < mb_threshold:
                    size_str = f"{size / kb_threshold:.1f}KB"
                else:
                    size_str = f"{size / mb_threshold:.1f}MB"

                results.append(f"[FILE] {relative} ({size_str})")

        if not results:
            return "No items found matching criteria"

        header = f"Contents of {dir_path}:\n"
        if pattern:
            header += f"Pattern: {pattern}\n"

        return header + "\n".join(results)

    except PermissionError:
        return f"Error: Permission denied: {path}"
    except Exception:
        from matilda_brain.utils import get_logger

        get_logger(__name__).exception("Error listing directory")
        return "Error listing directory - see logs for details"


__all__ = ["read_file", "write_file", "list_directory"]
