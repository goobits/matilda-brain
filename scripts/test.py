#!/usr/bin/env python3
"""Unified test runner for offline, mocked-integration, and real-API suites."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tomllib
import venv
from pathlib import Path


def _get_version() -> str:
    try:
        with open(Path(__file__).resolve().parents[1] / "pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        return str(data["project"]["version"])
    except Exception:
        return "unknown"


VERSION = _get_version()

REPO_ROOT = Path(__file__).resolve().parents[1]


def _test_env_python() -> Path:
    relative_path = Path("Scripts/python.exe") if os.name == "nt" else Path("bin/python")
    return REPO_ROOT / ".artifacts" / "test" / "test-env" / relative_path


def _ensure_test_env() -> None:
    """Ensure we run tests in a pinned, isolated env.

    This avoids leaking whatever pytest plugins happen to be installed globally,
    and keeps CI/dev output warning-free (without filtering warnings away).
    """
    if os.environ.get("MATILDA_BRAIN_TEST_ENV") == "1":
        return

    py = _test_env_python()
    env_dir = py.parent.parent

    if not py.exists():
        env_dir.mkdir(parents=True, exist_ok=True)
        venv.EnvBuilder(with_pip=True, clear=False).create(env_dir)

    env = os.environ.copy()
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"

    # Install local deps + pinned dev extras so tests run with consistent versions.
    # Note: Brain depends on `matilda-transport`, which isn't published to PyPI.
    transport_dir = REPO_ROOT.parent / "matilda-transport"
    if transport_dir.is_dir():
        subprocess.run(
            [str(py), "-m", "pip", "install", "-q", "--disable-pip-version-check", "-e", str(transport_dir)],
            env=env,
            check=True,
        )
    subprocess.run(
        [str(py), "-m", "pip", "install", "-q", "--disable-pip-version-check", "-e", ".[dev]"],
        cwd=str(REPO_ROOT),
        env=env,
        check=True,
    )

    # Re-exec under the test env interpreter for consistent plugin resolution.
    env["MATILDA_BRAIN_TEST_ENV"] = "1"
    os.execve(str(py), [str(py), str(Path(__file__).resolve()), *sys.argv[1:]], env)


def show_examples() -> None:
    """Show comprehensive usage examples."""
    examples = """
🧪 MATILDA BRAIN TEST RUNNER

BASIC USAGE:
  ./test.py                                    # Run unit tests (default)
  ./test.py unit                               # Run unit tests explicitly
  ./test.py integration                        # Run integration tests with HTTP mocks
  ./test.py integration --real-api             # Run paid/network integration tests
  ./test.py all                                # Run unit + mocked integration tests

OPTIONS:
  ./test.py --coverage                         # Generate coverage report
  ./test.py -c                                 # Short form for coverage
  ./test.py --verbose                          # Verbose output
  ./test.py --parallel                         # Run tests in parallel (auto workers)
  ./test.py --parallel 4                       # Run tests with 4 workers
  ./test.py --test test_api                    # Run specific test pattern
  ./test.py --markers "not slow"               # Filter by markers
  ./test.py --force                            # Skip real-API confirmation prompts

EXAMPLES:
  ./test.py unit --coverage --verbose          # Unit tests with coverage
  ./test.py unit --parallel                    # Fast parallel unit tests
  ./test.py integration --real-api --force     # Paid integration without prompt
  ./test.py all --real-api --force             # Unit + paid integration

COST INFORMATION:
  - Unit tests: FREE (uses mocked API calls)
  - Integration tests: ~$0.01-$0.10 (real API calls)

API KEYS (for integration tests):
  - OPENAI_API_KEY
  - ANTHROPIC_API_KEY
  - OPENROUTER_API_KEY
"""
    print(examples)


def check_api_keys() -> bool:
    """Check for available API keys and print status."""
    keys = {
        "OPENAI_API_KEY": "OpenAI",
        "ANTHROPIC_API_KEY": "Anthropic",
        "OPENROUTER_API_KEY": "OpenRouter",
    }
    found = []
    for env_var, name in keys.items():
        if os.environ.get(env_var):
            print(f"✅ {name} API key found")
            found.append(name)

    if not found:
        print("⚠️  No API keys found")
        print("Set one or more of:")
        for env_var in keys:
            print(f"  - {env_var}")
        return False
    return True


def check_virtual_env() -> None:
    """Check if running in a virtual environment."""
    if os.environ.get("VIRTUAL_ENV"):
        venv_name = os.path.basename(os.environ["VIRTUAL_ENV"])
        print(f"✅ Virtual environment: {venv_name}")
    elif os.path.exists(".venv"):
        print("💡 Virtual environment available but not activated")
        print("   Consider running: source .venv/bin/activate")


def check_xdist() -> bool:
    """Check if pytest-xdist is available."""
    import importlib.util

    return importlib.util.find_spec("xdist") is not None


def build_pytest_cmd(args: argparse.Namespace, test_type: str) -> list[str]:
    """Build the pytest command based on arguments and test type."""
    cmd = [sys.executable, "-m", "pytest"]

    # Test path or pattern
    if args.test:
        cmd.extend(["tests/", "-k", args.test])
    elif test_type == "unit":
        cmd.extend(["tests/unit/"])
    elif test_type == "integration":
        cmd.extend(["tests/integration/"])
    else:
        cmd.append("tests/")

    # Markers
    if args.markers:
        cmd.extend(["-m", args.markers])

    if args.real_api and test_type == "integration":
        cmd.append("--real-api")

    # Verbose
    if args.verbose:
        cmd.append("-v")

    # Coverage
    if args.coverage:
        cmd.extend(
            ["--cov=src/matilda_brain", "--cov-report=term-missing", "--cov-report=html:.artifacts/coverage/html"]
        )
        if getattr(args, "coverage_append", False):
            cmd.append("--cov-append")
        print("📊 Coverage report will be generated in .artifacts/coverage/html/")

    # Parallel execution
    if args.parallel != "off":
        if check_xdist():
            workers = "auto" if args.parallel == "auto" else args.parallel
            cmd.extend(["-n", workers])
            print(f"🚀 Running tests in parallel ({workers} workers)")
        else:
            print("⚠️  pytest-xdist not installed, running sequentially")
            print("   Install with: pip install pytest-xdist")

    return cmd


def run_tests(cmd: list[str], *, include_external: bool = False, real_api: bool = False) -> int:
    """Run pytest with the given command."""
    print(f"Running: {' '.join(cmd)}")
    print()
    env = os.environ.copy()
    if include_external:
        env["BRAIN_RUN_CRED_TESTS"] = "1"
    if real_api:
        env["REAL_API_TESTS"] = "1"
    local_transport = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "matilda-transport", "src"))
    if os.path.isdir(local_transport):
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{local_transport}{os.pathsep}{existing}" if existing else local_transport
    sys.stdout.flush()
    result = subprocess.run(cmd, env=env)
    return result.returncode


def run_unit_tests(args: argparse.Namespace) -> int:
    """Run unit tests."""
    print("🧪 Running Unit Tests")
    print("=" * 40)
    print()

    cmd = build_pytest_cmd(args, "unit")
    exit_code = run_tests(cmd)

    print()
    if exit_code == 0:
        print("✅ Unit tests passed!")
        if args.coverage:
            print("📊 Coverage report: .artifacts/coverage/html/index.html")
    else:
        print(f"❌ Unit tests failed (exit code: {exit_code})")

    return exit_code


def run_integration_tests(args: argparse.Namespace) -> int:
    """Run integration tests."""
    print("🧪 Running Integration Tests")
    print("=" * 40)
    print()

    if args.real_api and not check_api_keys():
        print("❌ Real API tests require at least one configured provider key.")
        return 2

    if args.real_api:
        print()
        print("⚠️  WARNING: These tests will make real API calls and consume credits!")
        print("💰 Estimated cost: $0.01 - $0.10 depending on models used")
        print()
    else:
        print("Using deterministic HTTP mocks; no provider charges will be incurred.")
        print()

    if args.real_api and not args.force:
        try:
            response = input("Continue with integration tests? [y/N]: ").strip().lower()
            if response != "y":
                print("Integration tests cancelled.")
                return 0
        except (EOFError, KeyboardInterrupt):
            print("\nIntegration tests cancelled.")
            return 0

    print()
    cmd = build_pytest_cmd(args, "integration")
    exit_code = run_tests(cmd, include_external=True, real_api=args.real_api)

    print()
    if exit_code == 0:
        print("✅ Integration tests passed!")
    else:
        print(f"❌ Integration tests failed (exit code: {exit_code})")

    return exit_code


def main() -> int:
    """Main entry point."""
    _ensure_test_env()

    # Custom help
    if len(sys.argv) == 2 and sys.argv[1] in ["-h", "--help"]:
        show_examples()
        return 0

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "command", nargs="?", default="unit", choices=["unit", "integration", "all", "help"], help="Test type to run"
    )
    parser.add_argument("--coverage", "-c", action="store_true", help="Generate coverage report")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose test output")
    parser.add_argument(
        "--parallel",
        "-p",
        nargs="?",
        const="auto",
        default="off",
        help="Run tests in parallel (N workers, default: auto)",
    )
    parser.add_argument("--test", "-t", help="Run specific test file or pattern")
    parser.add_argument("--markers", "-m", help="Run tests matching marker expression")
    parser.add_argument("--force", "-f", action="store_true", help="Skip confirmation prompts")
    parser.add_argument("--real-api", action="store_true", help="Use real provider APIs instead of HTTP mocks")
    parser.add_argument("--version", action="store_true", help="Show version")

    args = parser.parse_args()

    if args.version:
        print(f"Matilda Brain Test Runner v{VERSION}")
        return 0

    if args.command == "help":
        show_examples()
        return 0

    print(f"🧪 Matilda Brain Test Runner v{VERSION}")
    print("=" * 40)
    print()

    check_virtual_env()
    print()

    # Check pytest is available
    import importlib.util

    if importlib.util.find_spec("pytest") is None:
        print("❌ pytest not found!")
        print("Install with: pip install pytest pytest-asyncio pytest-cov")
        return 1

    if args.command == "unit":
        return run_unit_tests(args)
    elif args.command == "integration":
        return run_integration_tests(args)
    elif args.command == "all":
        print("Running all test types...")
        print()

        exit_code = run_unit_tests(args)
        if exit_code != 0:
            print()
            print("❌ Unit tests failed! Skipping integration tests.")
            return exit_code

        print()
        args.force = True  # Skip prompt for subsequent tests
        args.coverage_append = args.coverage
        exit_code = run_integration_tests(args)

        if exit_code == 0:
            print()
            print("🎉 All tests passed!")

        return exit_code

    return 0


if __name__ == "__main__":
    sys.exit(main())
