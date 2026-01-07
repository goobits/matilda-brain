"""Test to verify HTTP mocking is working correctly."""

from unittest.mock import AsyncMock, patch

import pytest
from tests.utils.http_mocks import get_http_mocker, reset_http_mocker


@pytest.fixture(autouse=True)
def mock_litellm_acompletion():
    """Ensure LiteLLM calls are mocked for this module."""
    reset_http_mocker()
    mocker = get_http_mocker()

    async def mock_acompletion(*args, **kwargs):
        return await mocker.mock_acompletion(*args, **kwargs)

    class FakeLiteLLM:
        def __init__(self):
            self.acompletion = AsyncMock(side_effect=mock_acompletion)

    with patch.dict("sys.modules", {"litellm": FakeLiteLLM()}):
        from matilda_brain.backends.cloud import CloudBackend
        from matilda_brain.core.routing import router

        cloud_backend = CloudBackend()
        with patch.object(router, "smart_route", return_value=(cloud_backend, "gpt-3.5-turbo")):
            yield


class TestMockVerification:
    """Verify that the HTTP mocking system works correctly."""

    def test_mock_is_active_by_default(self, delayed_ask):
        """Test that mocks are active by default for integration tests."""
        # Make a request
        response = delayed_ask("What is 2+2?", model="gpt-3.5-turbo")

        # Verify mock returned expected response
        assert str(response) == "4"
        assert response.succeeded
        assert response.model == "gpt-3.5-turbo"

        # Get mocker to check if it was called
        mocker = get_http_mocker()
        assert mocker.call_count >= 1

    def test_context_awareness_in_chat(self, delayed_chat):
        """Test that mocks understand chat context."""
        with delayed_chat(model="gpt-3.5-turbo") as session:
            # First message establishes context
            response1 = session.ask("My name is Alice. What's 5+5?")
            assert "10" in str(response1)

            # Second message should remember context
            response2 = session.ask("What did I say my name was?")
            assert "alice" in str(response2).lower()

        # Get mocker to verify calls were made
        mocker = get_http_mocker()
        assert mocker.call_count >= 2

    def test_streaming_mock_works(self, delayed_stream):
        """Test that streaming mocks work correctly."""
        chunks = []
        for chunk in delayed_stream("Count from 1 to 3", model="gpt-3.5-turbo"):
            chunks.append(chunk)

        full_response = "".join(chunks)
        assert "1" in full_response
        assert "2" in full_response
        assert "3" in full_response

        # Get mocker to verify calls were made
        mocker = get_http_mocker()
        assert mocker.call_count >= 1

    def test_different_models_work(self, delayed_ask):
        """Test that different model names work with mocks."""
        # Test OpenRouter model
        response1 = delayed_ask("Hello", model="openrouter/google/gemini-2.5-flash")
        assert response1.succeeded

        # Test Claude model
        response2 = delayed_ask("Hello", model="claude-3-haiku-20240307")
        assert response2.succeeded

        # Get mocker to verify calls were made
        mocker = get_http_mocker()
        assert mocker.call_count >= 2


def test_real_api_bypass_env_var(monkeypatch):
    """Test that REAL_API_TESTS=1 bypasses mocking."""
    from tests.conftest import _should_use_real_api

    # Test default behavior
    assert not _should_use_real_api()

    # Test environment variable bypass
    monkeypatch.setenv("REAL_API_TESTS", "1")
    assert _should_use_real_api()


def test_real_api_bypass_config():
    """Test that --real-api flag bypasses mocking."""
    from tests.conftest import _should_use_real_api
    from unittest.mock import Mock

    # Mock config object
    config = Mock()
    config.getoption.return_value = True

    assert _should_use_real_api(config)
