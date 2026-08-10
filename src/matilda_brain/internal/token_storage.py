"""
Persistent API token storage for matilda-brain server.

Provides secure token management with the following priority:
1. MATILDA_API_TOKEN environment variable (highest priority)
2. Persistent token file at ~/.config/matilda/.api_token
3. Generate and persist new token if neither exists
"""

import os
import secrets
from pathlib import Path
from typing import Optional


def _get_config_dir() -> Path:
    """Get the config directory path (XDG-compliant)."""
    xdg_config = os.getenv("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config) / "matilda"
    return Path.home() / ".config" / "matilda"


def _get_token_file_path() -> Path:
    """Get the path to the persistent token file."""
    return _get_config_dir() / ".api_token"


def _read_token_from_file() -> Optional[str]:
    """Read token from persistent storage if it exists."""
    token_path = _get_token_file_path()
    if token_path.is_symlink():
        return None

    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(token_path, flags)
        try:
            if hasattr(os, "fchmod"):
                try:
                    os.fchmod(descriptor, 0o600)
                except (OSError, NotImplementedError):
                    pass
            token_file = os.fdopen(descriptor, encoding="utf-8")
            descriptor = -1
            with token_file:
                token = token_file.read().strip()
        finally:
            if descriptor >= 0:
                os.close(descriptor)
    except OSError:
        return None

    if token:
        return token
    return None


def _write_token_to_file(token: str) -> bool:
    """
    Write token to persistent storage.

    Returns True if successful, False otherwise.
    """
    token_path = _get_token_file_path()
    config_dir = token_path.parent

    try:
        config_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(token_path, flags, 0o600)
        try:
            token_file = os.fdopen(descriptor, "w", encoding="utf-8")
            descriptor = -1
            with token_file:
                token_file.write(token)
        finally:
            if descriptor >= 0:
                os.close(descriptor)

        return True
    except OSError:
        return False


def get_or_create_token() -> str:
    """
    Get or create the API token.

    Priority:
    1. MATILDA_API_TOKEN environment variable (highest priority)
    2. Persistent token file at ~/.config/matilda/.api_token
    3. Generate new token and persist it

    Returns:
        The API token string.
    """
    # 1. Check environment variable (highest priority)
    env_token = os.getenv("MATILDA_API_TOKEN", "").strip()
    if env_token:
        return env_token

    # 2. Check persistent token file
    file_token = _read_token_from_file()
    if file_token:
        return file_token

    # 3. Generate new token and persist it
    new_token = secrets.token_hex(32)
    token_path = _get_token_file_path()

    if _write_token_to_file(new_token):
        print(f"Generated new API token and saved to: {token_path}")
        print("Set MATILDA_API_TOKEN environment variable to use a custom token.")
        return new_token

    raced_token = _read_token_from_file()
    if raced_token:
        return raced_token
    raise RuntimeError("Could not securely persist an API token; set MATILDA_API_TOKEN explicitly")
