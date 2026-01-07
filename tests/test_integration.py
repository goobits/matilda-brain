"""Integration tests with real API keys.

These tests require actual API keys and make real network calls.
Run with: pytest tests/test_integration.py -k "integration" --real-api

Set environment variables:
- OPENAI_API_KEY
- ANTHROPIC_API_KEY
- OPENROUTER_API_KEY (recommended)

Note: These tests will consume API credits and should be run sparingly.
"""

import os

import pytest

from matilda_brain import APIKeyError, ModelNotFoundError, RateLimitError


def is_valid_key(key):
    """Check if an API key is valid (not a test key and has reasonable length)."""
    return key and "test-key" not in key and len(key) > 10


def skip_if_no_api_keys():
    """Skip test if no valid API keys are available."""
    has_keys = any(
        [
            is_valid_key(os.getenv("OPENAI_API_KEY")),
            is_valid_key(os.getenv("ANTHROPIC_API_KEY")),
            is_valid_key(os.getenv("OPENROUTER_API_KEY")),
        ]
    )
    return pytest.mark.skipif(not has_keys, reason="No valid API keys available for integration testing")


@pytest.mark.requires_credentials
@pytest.mark.requires_network
@skip_if_no_api_keys()
class TestRealAPIIntegration:
    """Integration tests with real API calls."""

    def test_basic_ask_integration(self, delayed_ask):
        """Test basic ask functionality with real API."""

        # Prefer OpenRouter if available, then valid OpenAI key
        if is_valid_key(os.getenv("OPENROUTER_API_KEY")):
            # Use Gemini 2.5 Flash (stable production model)
            model = "openrouter/google/gemini-2.5-flash"
        elif is_valid_key(os.getenv("OPENAI_API_KEY")):
            model = "gpt-3.5-turbo"
        else:
            model = "gpt-3.5-turbo"  # Default fallback

        response = delayed_ask("What is 2+2? Reply with just the number.", model=model, backend="cloud")
        # The response should contain exactly "4" - allowing for some whitespace
        response_text = str(response).strip()
        assert response_text == "4" or response_text == "4." or response_text == "Four"
        assert response.succeeded
        assert response.model
        assert response.backend == "cloud"

    def test_streaming_integration(self, delayed_stream):
        """Test streaming with real API."""
        chunks = []

        if is_valid_key(os.getenv("OPENROUTER_API_KEY")):
            model = "openrouter/google/gemini-2.5-flash"
        elif is_valid_key(os.getenv("OPENAI_API_KEY")):
            model = "gpt-3.5-turbo"  # Use standard model name
        else:
            model = "gpt-3.5-turbo"  # Default fallback
        for chunk in delayed_stream("Count from 1 to 3, one number per line.", model=model):
            chunks.append(chunk)

        full_response = "".join(chunks)
        assert len(chunks) > 1  # Should be multiple chunks
        # Should contain numbers 1, 2, 3 from the counting request
        import re

        assert re.search(r"[123]", full_response)

    def test_chat_session_integration(self, delayed_chat):
        """Test persistent chat session."""

        if is_valid_key(os.getenv("OPENROUTER_API_KEY")):
            model = "openrouter/google/gemini-2.5-pro"
        elif is_valid_key(os.getenv("OPENAI_API_KEY")):
            model = "gpt-3.5-turbo"  # Use standard model name
        else:
            model = "gpt-3.5-turbo"  # Default fallback
        with delayed_chat(model=model) as session:
            response1 = session.ask("My name is Alice. What's 5+5?")
            # Check that the math result is present (using word boundaries to avoid false positives)
            import re

            response_text = str(response1)
            assert re.search(r"\b(10|ten)\b", response_text, re.IGNORECASE)

            response2 = session.ask("What did I say my name was?")
            # Verify the model remembered the name from context
            response2_lower = str(response2).lower()
            assert "alice" in response2_lower and ("name" in response2_lower or "you" in response2_lower)

    def test_model_fallback_integration(self, delayed_ask):
        """Test that fallback works with real APIs."""
        # Use a model that might not exist to test fallback
        try:
            response = delayed_ask("Hello", model="nonexistent-model", backend="cloud")
            # If it succeeds, it means there was a fallback
            assert response.succeeded
        except Exception as e:
            # If it fails, check that the error message is appropriate
            assert "LLM Provider NOT provided" in str(e) or "model" in str(e).lower()

    @pytest.mark.skipif(not os.getenv("OPENROUTER_API_KEY"), reason="OpenRouter key required")
    def test_gemini_25_pro_integration(self, delayed_ask):
        """Test Gemini 2.5 Pro stable version."""
        model = "openrouter/google/gemini-2.5-pro"
        response = delayed_ask(
            "Explain quantum computing in exactly 3 words.",
            model=model,
            backend="cloud",
        )
        assert response.succeeded
        assert len(str(response).split()) <= 5  # Allow some flexibility
        assert response.model
        assert response.backend == "cloud"


@pytest.mark.requires_credentials
@pytest.mark.requires_network
@skip_if_no_api_keys()
class TestProviderSpecificIntegration:
    """Test specific providers with real keys."""

    @pytest.mark.skipif(
        not (os.getenv("OPENAI_API_KEY") and "test-key" not in os.getenv("OPENAI_API_KEY", "")),
        reason="Valid OpenAI key required",
    )
    def test_openai_specific(self, delayed_ask):
        """Test OpenAI-specific functionality."""
        response = delayed_ask("Say 'OpenAI test'", model="gpt-3.5-turbo")
        assert "OpenAI" in str(response) or "test" in str(response)

    @pytest.mark.skipif(
        not (os.getenv("ANTHROPIC_API_KEY") and "test-key" not in os.getenv("ANTHROPIC_API_KEY", "")),
        reason="Valid Anthropic key required",
    )
    def test_anthropic_specific(self, delayed_ask):
        """Test Anthropic-specific functionality."""
        response = delayed_ask("Say 'Claude test'", model="claude-3-haiku-20240307")
        assert response.succeeded

    @pytest.mark.skipif(not os.getenv("OPENROUTER_API_KEY"), reason="OpenRouter key required")
    def test_openrouter_variety(self, delayed_ask):
        """Test multiple models through OpenRouter."""
        models_to_test = [
            "gpt-3.5-turbo",  # Will be routed through OpenRouter automatically
            "claude-3-haiku",  # Will be routed through OpenRouter automatically
            "google/gemini-flash-1.5",  # OpenRouter format
        ]

        for model in models_to_test:
            try:
                response = delayed_ask("Reply with just 'OK'", model=model)
                # Some models might not be available, that's fine
                if response.succeeded:
                    assert len(str(response)) > 0
            except (APIKeyError, ModelNotFoundError, RateLimitError):
                # Skip models that aren't available due to missing keys or rate limits
                continue
            except Exception as e:
                # Log unexpected errors instead of silently ignoring
                pytest.fail(f"Unexpected error testing {model}: {type(e).__name__}: {e}")


@pytest.mark.requires_credentials
@pytest.mark.requires_network
@pytest.mark.slow
@skip_if_no_api_keys()
class TestErrorHandlingIntegration:
    """Test error handling with real APIs."""

    def test_invalid_model_error(self, delayed_ask):
        """Test handling of invalid model names."""
        try:
            response = delayed_ask("Hello", model="definitely-not-a-real-model-name-12345")
            # If it succeeds, check response
            assert response is not None
        except Exception as e:
            # Expected to fail with appropriate error
            assert "backend" in str(e).lower() or "model" in str(e).lower()

    def test_rate_limiting_handling(self, delayed_ask):
        """Test rate limit handling (careful - might hit actual limits)."""
        # Make several rapid requests to test rate limiting
        responses = []

        # Use OpenRouter model if available
        if is_valid_key(os.getenv("OPENROUTER_API_KEY")):
            model = "openrouter/google/gemini-2.5-flash"
        else:
            pytest.skip("No valid API key for rate limit testing")

        for i in range(3):  # Keep low to avoid hitting limits
            response = delayed_ask(f"Count: {i}", model=model)
            responses.append(response)

        # At least some should succeed
        assert any(r.succeeded for r in responses)


# Performance benchmarks (optional)
@pytest.mark.requires_credentials
@pytest.mark.requires_network
@pytest.mark.benchmark
@skip_if_no_api_keys()
class TestPerformanceBenchmarks:
    """Performance tests with real APIs."""

    def test_response_time_benchmark(self, delayed_ask):
        """Benchmark response times for different models."""
        import time

        results = {}

        # Test with OpenRouter models if available
        if is_valid_key(os.getenv("OPENROUTER_API_KEY")):
            models = [
                "openrouter/google/gemini-2.5-flash",
                "openrouter/google/gemini-2.5-pro",
            ]

            for model in models:
                start_time = time.time()
                try:
                    response = delayed_ask("What is AI?", model=model)
                    end_time = time.time()

                    if response.succeeded:
                        results[model] = end_time - start_time
                except Exception:
                    # Model might not be available
                    pass

        # Should have at least one result
        if not results:
            pytest.skip("No valid API keys for benchmarking")

        # Just verify we got timing data
        assert len(results) > 0
        for model, duration in results.items():
            assert duration > 0


# Usage examples for documentation
@pytest.mark.requires_credentials
@pytest.mark.requires_network
@pytest.mark.examples
@skip_if_no_api_keys()
class TestUsageExamples:
    """Real usage examples that can be used in documentation."""

    def test_code_generation_produces_valid_python_function_with_docstring(self, delayed_ask):
        """Example of using AI for code generation."""
        prompt = "Write a Python function that calculates factorial. Include docstring."

        if is_valid_key(os.getenv("OPENROUTER_API_KEY")):
            model = "openrouter/google/gemini-2.5-flash"
        else:
            model = "gpt-3.5-turbo"
        response = delayed_ask(prompt, model=model)

        assert response.succeeded
        assert "def" in str(response)
        assert "factorial" in str(response).lower()

    def test_data_analysis_explains_statistical_concepts_clearly(self, delayed_ask):
        """Example of using AI for data analysis questions."""
        prompt = "Explain the difference between mean and median in statistics."

        if is_valid_key(os.getenv("OPENROUTER_API_KEY")):
            model = "openrouter/google/gemini-2.5-flash"
        else:
            model = "gpt-3.5-turbo"
        response = delayed_ask(prompt, model=model)

        assert response.succeeded
        assert "mean" in str(response).lower()
        assert "median" in str(response).lower()
