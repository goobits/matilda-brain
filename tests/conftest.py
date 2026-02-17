"""Pytest configuration file."""

import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Add the parent directory and src directory to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root))

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

SHARED_CONFIG_PATH = Path(__file__).resolve().parents[2] / "matilda" / "config.toml"
os.environ.setdefault("MATILDA_CONFIG", str(SHARED_CONFIG_PATH))


@pytest.fixture(scope="session", autouse=True)
def shared_config_env():
    """Point tests at the shared TOML config."""
    return SHARED_CONFIG_PATH


# Configuration for rate limiting delays
OPENROUTER_DEFAULT_DELAY = 1.0  # Default 1 second delay between OpenRouter API calls
OPENAI_DEFAULT_DELAY = 0.5  # Default 0.5 second delay between OpenAI API calls
ANTHROPIC_DEFAULT_DELAY = 0.5  # Default 0.5 second delay between Anthropic API calls
CONSERVATIVE_DEFAULT_DELAY = 1.0  # Conservative default delay for unknown providers

# Smart rate limiting configuration
MIN_DELAY = 0.1  # Minimum delay for progressive rate limiting
MAX_DELAY = 2.0  # Maximum delay for progressive rate limiting


def _should_skip_rate_limiting(config=None):
    """Determine if rate limiting should be skipped based on environment.

    Returns True if:
    - Fast mode is enabled (--fast flag or PYTEST_FAST_MODE=1)
    - Running in CI environment
    - No real API keys present (all tests would be mocked)
    - Explicit disable flag is set
    - Running unit tests only
    """
    # Check for fast mode first
    if os.getenv("PYTEST_FAST_MODE") == "1":
        return True

    if config and config.getoption("--fast", default=False):
        return True

    # Check for CI environment
    if os.getenv("CI") or os.getenv("GITHUB_ACTIONS") or os.getenv("PYTEST_DISABLE_RATE_LIMIT"):
        return True

    # Check if any real API keys are present
    has_real_keys = any(
        [
            _is_valid_api_key(os.getenv("OPENAI_API_KEY")),
            _is_valid_api_key(os.getenv("ANTHROPIC_API_KEY")),
            _is_valid_api_key(os.getenv("OPENROUTER_API_KEY")),
            _is_valid_api_key(os.getenv("GOOGLE_API_KEY")),
        ]
    )

    # If no real API keys, all tests are mocked - skip delays
    return not has_real_keys


def _is_valid_api_key(key):
    """Check if an API key looks real (not a test key)."""
    if not key:
        return False
    key_lower = key.lower()
    # Common test/mock key patterns
    test_patterns = ["test", "mock", "fake", "demo", "example", "dummy"]
    return len(key) > 10 and not any(pattern in key_lower for pattern in test_patterns)


def _network_available() -> bool:
    """Best-effort network check for tests marked requires_network."""
    import socket

    try:
        with socket.create_connection(("1.1.1.1", 53), timeout=1):
            return True
    except OSError:
        return False


def pytest_collection_modifyitems(config, items):
    """Deselect tests that require unavailable external prerequisites.

    This keeps local suite runs deterministic without real credentials/network.
    Set BRAIN_RUN_CRED_TESTS=1 to include credential/network-marked tests.
    """
    if os.getenv("BRAIN_RUN_CRED_TESTS") == "1":
        return

    deselected = []
    kept = []
    for item in items:
        requires_credentials = item.get_closest_marker("requires_credentials") is not None
        requires_network = item.get_closest_marker("requires_network") is not None

        should_deselect = requires_credentials or requires_network

        if should_deselect:
            deselected.append(item)
        else:
            kept.append(item)

    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = kept


def _uses_mock_backend(request):
    """Check if the test is using a mock backend by examining fixtures and test content."""
    # Check if mock-related fixtures are used
    if hasattr(request, "fixturenames"):
        mock_fixtures = [name for name in request.fixturenames if "mock" in name.lower()]
        if mock_fixtures:
            return True

    # Check test function for mock usage
    if hasattr(request.node, "function") and hasattr(request.node.function, "__code__"):
        code_names = request.node.function.__code__.co_names
        mock_indicators = ["mock", "Mock", "patch", "MagicMock"]
        if any(indicator in code_names for indicator in mock_indicators):
            return True

    return False


@pytest.fixture
def rate_limit_delay(request):
    """Fixture to add delays between API calls to respect rate limits.

    Returns a function that adds appropriate delay based on the provider.
    Uses smart detection to skip delays when appropriate.
    """
    # Track delay counts for progressive limiting
    delay_count = 0

    def delay(provider=None, force=False):
        """Add delay based on provider to respect rate limits.

        Args:
            provider: The API provider name (openrouter, openai, anthropic, etc.)
                     If None, uses a conservative default delay.
            force: Force delay even if conditions suggest skipping
        """
        nonlocal delay_count

        # Skip delays in various conditions unless forced
        if not force:
            if _should_skip_rate_limiting(request.config):
                return
            if _uses_mock_backend(request):
                return

        # Calculate progressive delay
        if provider:
            provider_lower = provider.lower()
            if "openrouter" in provider_lower:
                base_delay = float(os.getenv("OPENROUTER_RATE_DELAY", OPENROUTER_DEFAULT_DELAY))
            elif "openai" in provider_lower or "gpt" in provider_lower:
                base_delay = float(os.getenv("OPENAI_RATE_DELAY", OPENAI_DEFAULT_DELAY))
            elif "anthropic" in provider_lower or "claude" in provider_lower:
                base_delay = float(os.getenv("ANTHROPIC_RATE_DELAY", ANTHROPIC_DEFAULT_DELAY))
            else:
                base_delay = CONSERVATIVE_DEFAULT_DELAY
        else:
            base_delay = CONSERVATIVE_DEFAULT_DELAY

        # Progressive delay: start small, increase if needed
        delay_multiplier = min(1.0 + (delay_count * 0.1), 2.0)  # Max 2x original delay
        actual_delay = max(MIN_DELAY, min(base_delay * delay_multiplier, MAX_DELAY))

        delay_count += 1
        time.sleep(actual_delay)

    return delay


@pytest.fixture(autouse=True)
def auto_rate_limit_for_integration_tests(request, rate_limit_delay):
    """Automatically add delays for integration tests that need real API calls.

    Uses smart detection to only delay tests that actually make API calls.
    """
    # Check if this is an integration test
    markers = request.node.iter_markers(name="integration")
    if not list(markers):
        return

    # Skip delays if conditions indicate this test doesn't need them
    if _should_skip_rate_limiting(request.config):
        return

    # Skip if test uses mocks
    if _uses_mock_backend(request):
        return

    # Check if test function explicitly uses --real-api flag
    real_api_flag = request.config.getoption("--real-api", default=False)
    if not real_api_flag and not any(
        [
            _is_valid_api_key(os.getenv("OPENAI_API_KEY")),
            _is_valid_api_key(os.getenv("ANTHROPIC_API_KEY")),
            _is_valid_api_key(os.getenv("OPENROUTER_API_KEY")),
        ]
    ):
        return

    # Add a minimal initial delay for real integration tests
    time.sleep(MIN_DELAY)


@pytest.fixture
def delayed_ask(rate_limit_delay):
    """Wrapper for the ask function that adds rate limit delays.

    Usage in tests:
        response = delayed_ask("Hello", model="gpt-3.5-turbo")
    """
    from matilda_brain import ask

    def _delayed_ask(*args, **kwargs):
        # Extract model to determine provider
        model = kwargs.get("model", "")
        if model:
            if "openrouter" in model:
                rate_limit_delay("openrouter")
            elif "gpt" in model:
                rate_limit_delay("openai")
            elif "claude" in model:
                rate_limit_delay("anthropic")
            else:
                rate_limit_delay()
        else:
            rate_limit_delay()

        return ask(*args, **kwargs)

    return _delayed_ask


@pytest.fixture
def delayed_stream(rate_limit_delay):
    """Wrapper for the stream function that adds rate limit delays.

    Usage in tests:
        for chunk in delayed_stream("Hello", model="gpt-3.5-turbo"):
            print(chunk)
    """
    from matilda_brain import stream

    def _delayed_stream(*args, **kwargs):
        # Extract model to determine provider
        model = kwargs.get("model", "")
        if model:
            if "openrouter" in model:
                rate_limit_delay("openrouter")
            elif "gpt" in model:
                rate_limit_delay("openai")
            elif "claude" in model:
                rate_limit_delay("anthropic")
            else:
                rate_limit_delay()
        else:
            rate_limit_delay()

        return stream(*args, **kwargs)

    return _delayed_stream


@pytest.fixture
def delayed_chat(rate_limit_delay):
    """Wrapper for the chat function that adds rate limit delays.

    Usage in tests:
        with delayed_chat(model="gpt-3.5-turbo") as session:
            response = session.ask("Hello")
    """
    from matilda_brain import chat

    class DelayedChatSession:
        def __init__(self, session, delay_func, model):
            self.session = session
            self.delay_func = delay_func
            self.model = model

        def ask(self, *args, **kwargs):
            # Add delay before each ask
            if "openrouter" in self.model:
                self.delay_func("openrouter")
            elif "gpt" in self.model:
                self.delay_func("openai")
            elif "claude" in self.model:
                self.delay_func("anthropic")
            else:
                self.delay_func()

            return self.session.ask(*args, **kwargs)

        def stream(self, *args, **kwargs):
            # Add delay before each stream
            if "openrouter" in self.model:
                self.delay_func("openrouter")
            elif "gpt" in self.model:
                self.delay_func("openai")
            elif "claude" in self.model:
                self.delay_func("anthropic")
            else:
                self.delay_func()

            return self.session.stream(*args, **kwargs)

        def clear(self):
            return self.session.clear()

    @contextmanager
    def _delayed_chat(*args, **kwargs):
        model = kwargs.get("model", "")

        # Add initial delay
        if "openrouter" in model:
            rate_limit_delay("openrouter")
        elif "gpt" in model:
            rate_limit_delay("openai")
        elif "claude" in model:
            rate_limit_delay("anthropic")
        else:
            rate_limit_delay()

        # Create chat session and wrap it
        with chat(*args, **kwargs) as session:
            yield DelayedChatSession(session, rate_limit_delay, model)

    return _delayed_chat


# Smart mocking for integration tests
def _should_use_real_api(config=None, env_override=None):
    """Determine if integration tests should use real API calls.

    Returns True if:
    - --real-api flag is used
    - REAL_API_TESTS=1 environment variable is set
    - env_override is explicitly True
    """
    # Check environment override first
    if env_override is not None:
        return env_override

    # Check command line flag
    if config and config.getoption("--real-api", default=False):
        return True

    # Check environment variable
    if os.getenv("REAL_API_TESTS") == "1":
        return True

    return False


@pytest.fixture(autouse=True)
def smart_integration_mocking(request, monkeypatch):
    """Automatically mock HTTP calls for integration tests unless real APIs are requested.

    This fixture:
    - Detects integration tests
    - Mocks litellm.acompletion by default
    - Allows real API calls when --real-api flag or REAL_API_TESTS=1 is used
    - Preserves all business logic and error handling
    """
    # Only apply to tests that are marked as integration-style
    marker_names = {marker.name for marker in request.node.iter_markers()}
    if not (
        "integration" in marker_names
        or "requires_credentials" in marker_names
        or "requires_network" in marker_names
        or "requires_service" in marker_names
        or "requires_gpu" in marker_names
    ):
        yield None
        return

    # Check if we should use real APIs
    use_real_api = _should_use_real_api(request.config)

    if use_real_api:
        # Don't mock anything - use real APIs
        yield None
        return

    # Import mocking utilities
    from tests.utils.http_mocks import get_http_mocker, reset_http_mocker
    from unittest.mock import patch, AsyncMock

    # Reset mocker state for clean test
    reset_http_mocker()
    mocker = get_http_mocker()

    # Mock litellm module directly where it's imported
    async def mock_acompletion(*args, **kwargs):
        return await mocker.mock_acompletion(*args, **kwargs)

    # Patch litellm module itself
    with patch("litellm.acompletion", new=AsyncMock(side_effect=mock_acompletion)) as mock_litellm:
        yield mock_litellm


@pytest.fixture
def mock_rate_limit_error():
    """Fixture to simulate rate limit errors in integration tests."""
    from tests.utils.http_mocks import ErrorHTTPMocker
    from unittest.mock import patch, AsyncMock

    error_mocker = ErrorHTTPMocker("rate_limit")

    async def mock_acompletion(*args, **kwargs):
        return await error_mocker.mock_acompletion(*args, **kwargs)

    with patch("litellm.acompletion", new=AsyncMock(side_effect=mock_acompletion)) as mock_litellm:
        yield mock_litellm


@pytest.fixture
def mock_auth_error():
    """Fixture to simulate authentication errors in integration tests."""
    from tests.utils.http_mocks import ErrorHTTPMocker
    from unittest.mock import patch, AsyncMock

    error_mocker = ErrorHTTPMocker("auth")

    async def mock_acompletion(*args, **kwargs):
        return await error_mocker.mock_acompletion(*args, **kwargs)

    with patch("litellm.acompletion", new=AsyncMock(side_effect=mock_acompletion)) as mock_litellm:
        yield mock_litellm


# Command line options
def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--real-api",
        action="store_true",
        default=False,
        help="Run tests that require real API keys",
    )
    parser.addoption(
        "--rate-delay",
        type=float,
        default=None,
        help="Override default rate limit delay (in seconds)",
    )
    parser.addoption(
        "--fast",
        action="store_true",
        default=False,
        help="Skip rate limiting delays for fast development cycles",
    )
