"""Chat session management for TTT CLI."""

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.table import Table

from ..utils import get_logger

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
        messages = [ChatMessage(**msg) for msg in data.get("messages", [])]
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
            self.sessions_dir = Path.home() / ".ttt" / "sessions"
        else:
            self.sessions_dir = Path(sessions_dir)

        # Ensure sessions directory exists
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def create_session(
        self,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        tools: Optional[List[str]] = None,
    ) -> ChatSession:
        """Create a new chat session."""
        now = datetime.utcnow().isoformat()
        session_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S_") + str(uuid.uuid4())[:8]

        session = ChatSession(
            id=session_id,
            created_at=now,
            updated_at=now,
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

        session_file = self.sessions_dir / f"{session_id}.json"

        if not session_file.exists():
            return None

        try:
            with open(session_file) as f:
                data = json.load(f)
            return ChatSession.from_dict(data)
        except Exception as e:
            logger.exception(f"Error loading session {session_id}")
            console.print(f"[red]Error loading session {session_id}: {e}[/red]")
            return None

    def load_last_session(self) -> Optional[ChatSession]:
        """Load the most recently modified session."""
        session_files = list(self.sessions_dir.glob("*.json"))

        if not session_files:
            return None

        # Sort by modification time, newest first
        latest_file = max(session_files, key=lambda f: f.stat().st_mtime)
        session_id = latest_file.stem

        return self.load_session(session_id)

    def save_session(self, session: ChatSession) -> None:
        """Save a session to disk."""
        session.updated_at = datetime.utcnow().isoformat()
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
            timestamp=datetime.utcnow().isoformat(),
            model=model,
        )
        session.messages.append(message)
        self.save_session(session)

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all available sessions with metadata."""
        sessions = []

        for session_file in self.sessions_dir.glob("*.json"):
            try:
                # Get basic info without loading full session
                session_file.stat()
                session_id = session_file.stem

                # Load just enough to get message count and last message
                with open(session_file) as f:
                    data = json.load(f)

                messages = data.get("messages", [])
                last_message = messages[-1] if messages else None

                sessions.append(
                    {
                        "id": session_id,
                        "created_at": data.get("created_at", "Unknown"),
                        "updated_at": data.get("updated_at", "Unknown"),
                        "message_count": len(messages),
                        "last_message": (
                            last_message.get("content", "")[:50] + "..." if last_message else "Empty session"
                        ),
                        "model": data.get("model", "default"),
                    }
                )
            except Exception as e:
                logger.exception(f"Could not read session {session_file.name}")
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

        session_file = self.sessions_dir / f"{session_id}.json"

        if session_file.exists():
            session_file.unlink()
            return True
        return False

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
