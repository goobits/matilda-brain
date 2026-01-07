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
    if token_path.exists():
        try:
            token = token_path.read_text().strip()
            if token:
                return token
        except (OSError, IOError):
            pass
    return None


def _write_token_to_file(token: str) -> bool:
    """
    Write token to persistent storage.

    Returns True if successful, False otherwise.
    """
    token_path = _get_token_file_path()
    config_dir = token_path.parent

    try:
        # Create config directory if it doesn't exist
        config_dir.mkdir(parents=True, exist_ok=True)

        # Write token to file
        token_path.write_text(token)

        # Set restrictive permissions (owner read/write only)
        try:
            token_path.chmod(0o600)
        except (OSError, NotImplementedError):
            # chmod may fail on Windows or some filesystems
            pass

        return True
    except (OSError, IOError):
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
    env_token = os.getenv("MATILDA_API_TOKEN")
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
    else:
        print("WARNING: Could not persist API token to file.")
        print(f"Generated temporary token: {new_token}")
        print("Set MATILDA_API_TOKEN in your environment for persistence.")

    return new_token
