import argparse
import importlib.util
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "test.py"
SPEC = importlib.util.spec_from_file_location("brain_test_runner", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
test_runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(test_runner)


def runner_args(**overrides):
    values = {
        "test": None,
        "markers": None,
        "real_api": False,
        "verbose": False,
        "coverage": False,
        "coverage_append": False,
        "parallel": "off",
        "force": True,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_real_api_flag_is_forwarded_only_to_integration_pytest():
    args = runner_args(real_api=True)

    assert "--real-api" not in test_runner.build_pytest_cmd(args, "unit")
    assert "--real-api" in test_runner.build_pytest_cmd(args, "integration")


def test_second_coverage_slice_appends_to_the_first():
    args = runner_args(coverage=True, coverage_append=True)

    command = test_runner.build_pytest_cmd(args, "integration")

    assert "--cov=src/matilda_brain" in command
    assert "--cov-append" in command


def test_run_tests_marks_external_and_real_api_modes(monkeypatch):
    captured = {}

    def fake_run(command, *, env):
        captured["command"] = command
        captured["env"] = env
        return argparse.Namespace(returncode=0)

    monkeypatch.setattr(test_runner.subprocess, "run", fake_run)

    assert test_runner.run_tests(["pytest"], include_external=True, real_api=True) == 0
    assert captured["command"] == ["pytest"]
    assert captured["env"]["BRAIN_RUN_CRED_TESTS"] == "1"
    assert captured["env"]["REAL_API_TESTS"] == "1"


def test_mocked_integration_explicitly_includes_external_markers(monkeypatch):
    captured = {}
    monkeypatch.setattr(test_runner, "build_pytest_cmd", lambda _args, _kind: ["pytest", "tests/integration"])

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return 0

    monkeypatch.setattr(test_runner, "run_tests", fake_run)

    assert test_runner.run_integration_tests(runner_args()) == 0
    assert captured == {
        "command": ["pytest", "tests/integration"],
        "kwargs": {"include_external": True, "real_api": False},
    }


def test_real_integration_fails_before_pytest_without_credentials(monkeypatch):
    monkeypatch.setattr(test_runner, "check_api_keys", lambda: False)
    monkeypatch.setattr(
        test_runner,
        "run_tests",
        lambda *_args, **_kwargs: pytest.fail("pytest must not run without credentials"),
    )

    assert test_runner.run_integration_tests(runner_args(real_api=True)) == 2
