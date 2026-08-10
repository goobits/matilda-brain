"""Persistent CLI session management for Matilda Brain."""

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.table import Table

from ..internal.utils import get_logger

logger = get_logger(__name__)
console = Console()


@dataclass
class ChatMessage:
    """Represents a single message in a chat session."""

    role: str  # 'user' or 'assistant'
    content: str
    timestamp: str
    model: Optional[str] = None


@dataclass
class ChatSession:
    """Represents a chat session."""

    id: str
    created_at: str
    updated_at: str
    messages: List[ChatMessage]
    model: Optional[str] = None
    system_prompt: Optional[str] = None
    tools: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": [asdict(msg) for msg in self.messages],
            "model": self.model,
            "system_prompt": self.system_prompt,
            "tools": self.tools,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatSession":
        """Create session from dictionary."""
        for key in ("id", "created_at", "updated_at"):
            if not isinstance(data.get(key), str):
                raise ValueError(f"Invalid session field: {key}")
        messages_data = data.get("messages", [])
        if not isinstance(messages_data, list) or not all(isinstance(message, dict) for message in messages_data):
            raise ValueError("Invalid session field: messages")
        messages = [ChatMessage(**message) for message in messages_data]
        return cls(
            id=data["id"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            messages=messages,
            model=data.get("model"),
            system_prompt=data.get("system_prompt"),
            tools=data.get("tools"),
        )


class ChatSessionManager:
    """Manages chat session persistence."""

    def __init__(self, sessions_dir: Optional[Path] = None):
        """Initialize the session manager."""
        if sessions_dir is None:
            self.sessions_dir = Path.home() / ".matilda" / "brain" / "sessions"
            self._legacy_sessions_dir: Optional[Path] = Path.home() / ".ttt" / "sessions"
        else:
            self.sessions_dir = Path(sessions_dir)
            self._legacy_sessions_dir = None

        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def _storage_dirs(self) -> tuple[Path, ...]:
        if self._legacy_sessions_dir is None:
            return (self.sessions_dir,)
        return (self.sessions_dir, self._legacy_sessions_dir)

    def _session_files(self) -> List[Path]:
        """Return canonical and legacy session files, preferring canonical duplicates."""
        files: List[Path] = []
        seen_ids: set[str] = set()
        for directory in self._storage_dirs():
            if not directory.is_dir():
                continue
            for session_file in directory.glob("*.json"):
                if session_file.stem not in seen_ids:
                    files.append(session_file)
                    seen_ids.add(session_file.stem)
        return files

    def _find_session_file(self, session_id: str) -> Optional[Path]:
        for directory in self._storage_dirs():
            session_file = directory / f"{session_id}.json"
            if session_file.exists():
                return session_file
        return None

    def create_session(
        self,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        tools: Optional[List[str]] = None,
    ) -> ChatSession:
        """Create a new chat session."""
        now = datetime.now(timezone.utc)
        session_id = now.strftime("%Y%m%d_%H%M%S_") + str(uuid.uuid4())[:8]

        session = ChatSession(
            id=session_id,
            created_at=now.isoformat(),
            updated_at=now.isoformat(),
            messages=[],
            model=model,
            system_prompt=system_prompt,
            tools=tools,
        )

        self._save_session(session)
        return session

    def _validate_session_id(self, session_id: str) -> None:
        """Validate session ID to prevent path traversal."""
        if not session_id or not session_id.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Invalid session ID")
        if ".." in session_id or "/" in session_id or "\\" in session_id:
            raise ValueError("Invalid session ID")

    def load_session(self, session_id: str) -> Optional[ChatSession]:
        """Load a session by ID."""
        try:
            self._validate_session_id(session_id)
        except ValueError:
            logger.warning(f"Invalid session ID attempt: {session_id}")
            return None

        session_file = self._find_session_file(session_id)
        if session_file is None:
            return None

        try:
            return self._load_session_file(session_file)
        except Exception as e:
            logger.exception("Error loading session %s", session_id)
            console.print(f"[red]Error loading session {session_id}: {e}[/red]")
            return None

    @staticmethod
    def _load_session_file(session_file: Path) -> ChatSession:
        with open(session_file) as file:
            data = json.load(file)
        if not isinstance(data, dict):
            raise ValueError("Session file must contain an object")
        return ChatSession.from_dict(data)

    def load_last_session(self) -> Optional[ChatSession]:
        """Load the most recently modified session."""
        session_files = self._session_files()

        if not session_files:
            return None

        # Sort by modification time, newest first
        latest_file = max(session_files, key=lambda f: f.stat().st_mtime)
        session_id = latest_file.stem

        return self.load_session(session_id)

    def save_session(self, session: ChatSession) -> None:
        """Save a session to disk."""
        session.updated_at = datetime.now(timezone.utc).isoformat()
        self._save_session(session)

    def _save_session(self, session: ChatSession) -> None:
        """Internal method to save session."""
        session_file = self.sessions_dir / f"{session.id}.json"

        try:
            with open(session_file, "w") as f:
                json.dump(session.to_dict(), f, indent=2)
        except PermissionError:
            logger.exception(f"Permission denied saving session to {session_file}")
            console.print(f"[red]Error: Permission denied saving session to {session_file}[/red]")
            raise
        except OSError as e:
            logger.exception(f"Could not save session to {session_file}")
            console.print(f"[red]Error: Could not save session to {session_file}: {e}[/red]")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error saving session {session.id}")
            console.print(f"[red]Error: Unexpected error saving session {session.id}: {e}[/red]")
            raise

    def add_message(self, session: ChatSession, role: str, content: str, model: Optional[str] = None) -> None:
        """Add a message to a session and save it."""
        message = ChatMessage(
            role=role,
            content=content,
            timestamp=datetime.now(timezone.utc).isoformat(),
            model=model,
        )
        session.messages.append(message)
        self.save_session(session)

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all available sessions with metadata."""
        sessions: List[Dict[str, Any]] = []

        for session_file in self._session_files():
            try:
                session = self._load_session_file(session_file)
                last_message = session.messages[-1] if session.messages else None

                sessions.append(
                    {
                        "id": session.id,
                        "created_at": session.created_at,
                        "updated_at": session.updated_at,
                        "message_count": len(session.messages),
                        "last_message": last_message.content[:50] + "..." if last_message else "Empty session",
                        "model": session.model,
                    }
                )
            except Exception as e:
                logger.exception("Could not read session %s", session_file.name)
                console.print(f"[yellow]Warning: Could not read session {session_file.name}: {e}[/yellow]")

        # Sort by updated_at, newest first
        sessions.sort(key=lambda x: x["updated_at"], reverse=True)
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        try:
            self._validate_session_id(session_id)
        except ValueError:
            return False

        deleted = False
        for directory in self._storage_dirs():
            session_file = directory / f"{session_id}.json"
            if session_file.exists():
                session_file.unlink()
                deleted = True
        return deleted

    def display_sessions_table(self) -> None:
        """Display all sessions in a nice table format."""
        sessions = self.list_sessions()

        if not sessions:
            console.print("[yellow]No chat sessions found.[/yellow]")
            return

        table = Table(title="Chat Sessions")
        table.add_column("Session ID", style="cyan")
        table.add_column("Created", style="green")
        table.add_column("Messages", justify="right", style="yellow")
        table.add_column("Model", style="blue")
        table.add_column("Last Message", style="white")

        for session in sessions[:20]:  # Show max 20 sessions
            created = session["created_at"]
            if "T" in created:
                # Parse and format the timestamp nicely
                try:
                    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    created = dt.strftime("%Y-%m-%d %H:%M")
                except (ValueError, TypeError, AttributeError):
                    # Keep original timestamp if parsing fails
                    pass

            table.add_row(
                session["id"],
                created,
                str(session["message_count"]),
                session["model"],
                session["last_message"],
            )

        console.print(table)

        if len(sessions) > 20:
            console.print(f"\n[dim]Showing 20 of {len(sessions)} sessions[/dim]")
