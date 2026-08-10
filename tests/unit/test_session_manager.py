import json
import os
from pathlib import Path

from matilda_brain.session.manager import ChatSession, ChatSessionManager


def test_session_manager_round_trip_and_summary(tmp_path):
    manager = ChatSessionManager(tmp_path)
    session = manager.create_session(model="test-model", system_prompt="Be concise", tools=["search"])

    manager.add_message(session, "user", "hello")
    manager.add_message(session, "assistant", "world", model="test-model")
    loaded = manager.load_session(session.id)

    assert isinstance(loaded, ChatSession)
    assert loaded.model == "test-model"
    assert loaded.system_prompt == "Be concise"
    assert loaded.tools == ["search"]
    assert [(message.role, message.content) for message in loaded.messages] == [
        ("user", "hello"),
        ("assistant", "world"),
    ]

    summaries = manager.list_sessions()
    assert summaries == [
        {
            "id": session.id,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "message_count": 2,
            "last_message": "world...",
            "model": "test-model",
        }
    ]

    assert manager.delete_session(session.id) is True
    assert manager.delete_session(session.id) is False
    assert manager.load_session(session.id) is None


def test_load_last_session_uses_file_modification_time(tmp_path):
    manager = ChatSessionManager(tmp_path)
    first = manager.create_session()
    second = manager.create_session()
    first_path = tmp_path / f"{first.id}.json"
    second_path = tmp_path / f"{second.id}.json"
    os.utime(first_path, (1, 1))
    os.utime(second_path, (2, 2))

    assert manager.load_last_session().id == second.id


def test_invalid_session_ids_cannot_escape_storage(tmp_path):
    manager = ChatSessionManager(tmp_path)
    outside = tmp_path.parent / "outside.json"
    outside.write_text("keep")

    for session_id in ("", "../outside", "nested/session", r"nested\session"):
        assert manager.load_session(session_id) is None
        assert manager.delete_session(session_id) is False

    assert outside.read_text() == "keep"


def test_corrupt_sessions_are_ignored_without_breaking_valid_ones(tmp_path):
    manager = ChatSessionManager(tmp_path)
    valid = manager.create_session(model="test-model")
    (tmp_path / "corrupt.json").write_text("not-json")
    (tmp_path / "wrong-shape.json").write_text(json.dumps({"messages": []}))

    assert manager.load_session("corrupt") is None
    assert [summary["id"] for summary in manager.list_sessions()] == [valid.id]


def test_default_storage_reads_legacy_sessions_and_writes_canonical_sessions(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    legacy_dir = tmp_path / ".ttt" / "sessions"
    legacy_dir.mkdir(parents=True)
    legacy_session = {
        "id": "legacy-session",
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
        "messages": [],
    }
    (legacy_dir / "legacy-session.json").write_text(json.dumps(legacy_session))

    manager = ChatSessionManager()

    assert manager.sessions_dir == tmp_path / ".matilda" / "brain" / "sessions"
    assert manager.load_session("legacy-session").id == "legacy-session"
    assert [session["id"] for session in manager.list_sessions()] == ["legacy-session"]

    created = manager.create_session()
    assert (manager.sessions_dir / f"{created.id}.json").exists()
    assert manager.delete_session("legacy-session") is True
    assert not (legacy_dir / "legacy-session.json").exists()
