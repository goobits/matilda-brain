import os

import pytest

from matilda_brain.internal import token_storage


def test_environment_token_takes_precedence(monkeypatch, tmp_path):
    monkeypatch.setenv("MATILDA_API_TOKEN", "  configured-token  ")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    assert token_storage.get_or_create_token() == "configured-token"
    assert not token_storage._get_token_file_path().exists()


def test_generated_token_is_private_and_reused(monkeypatch, tmp_path):
    monkeypatch.delenv("MATILDA_API_TOKEN", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(token_storage.secrets, "token_hex", lambda _length: "generated-token")

    assert token_storage.get_or_create_token() == "generated-token"
    token_path = token_storage._get_token_file_path()
    assert token_path.read_text() == "generated-token"
    if os.name != "nt":
        assert token_path.stat().st_mode & 0o777 == 0o600

    monkeypatch.setattr(token_storage.secrets, "token_hex", lambda _length: "different-token")
    assert token_storage.get_or_create_token() == "generated-token"


def test_token_symlink_is_never_followed(monkeypatch, tmp_path):
    monkeypatch.delenv("MATILDA_API_TOKEN", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    target = tmp_path / "target"
    target.write_text("target-secret")
    token_path = token_storage._get_token_file_path()
    token_path.parent.mkdir(parents=True)
    token_path.symlink_to(target)

    with pytest.raises(RuntimeError, match="MATILDA_API_TOKEN"):
        token_storage.get_or_create_token()

    assert target.read_text() == "target-secret"


def test_failed_persistence_never_prints_the_temporary_token(monkeypatch, capsys):
    monkeypatch.delenv("MATILDA_API_TOKEN", raising=False)
    monkeypatch.setattr(token_storage, "_read_token_from_file", lambda: None)
    monkeypatch.setattr(token_storage, "_write_token_to_file", lambda _token: False)
    monkeypatch.setattr(token_storage.secrets, "token_hex", lambda _length: "must-not-leak")

    with pytest.raises(RuntimeError, match="MATILDA_API_TOKEN"):
        token_storage.get_or_create_token()

    captured = capsys.readouterr()
    assert "must-not-leak" not in captured.out
    assert "must-not-leak" not in captured.err
