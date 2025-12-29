#!/usr/bin/env python3
"""
Advanced features examples for the AI library.

This script demonstrates advanced functionality including:
- Multi-modal AI (vision capabilities)
- Comprehensive exception handling
- Production-ready error handling patterns
- Advanced model selection and routing
"""

import os
from pathlib import Path

from matilda_brain import (
    # Import all exception types
    AIError,
    APIKeyError,
    BackendConnectionError,
    BackendNotAvailableError,
    BackendTimeoutError,
    ConfigFileError,
    EmptyResponseError,
    ImageInput,
    InvalidParameterError,
    InvalidPromptError,
    ModelNotFoundError,
    ModelNotSupportedError,
    MultiModalError,
    PersistentChatSession,
    QuotaExceededError,
    RateLimitError,
    SessionLoadError,
    SessionSaveError,
    ask,
    chat,
    configure,
    stream,
)


def basic_image_analysis():
    """Basic image analysis with vision models."""
    print("=== Basic Image Analysis ===\n")

    try:
        # Using a public image URL
        response = ask(
            [
                "What's in this image? Describe what you see in detail.",
                ImageInput(
                    "https://upload.wikimedia.org/wikipedia/commons/thumb/2/26/YellowLabradorLooking_new.jpg/640px-YellowLabradorLooking_new.jpg"
                ),
            ],
            model="gpt-4-vision-preview",
        )

        print(f"Response: {response}")
        print(f"Model used: {response.model}")
        print(f"Time taken: {response.time:.2f}s")

    except Exception as e:
        print(f"Image analysis failed: {e}")
        print("This requires a vision-capable model and API key")

    print()


def multiple_images_comparison():
    """Compare multiple images."""
    print("=== Multiple Images Comparison ===\n")

    try:
        response = ask(
            [
                "Compare these two images. What breed of dog do you see in each?",
                ImageInput(
                    "https://upload.wikimedia.org/wikipedia/commons/thumb/2/26/YellowLabradorLooking_new.jpg/640px-YellowLabradorLooking_new.jpg"
                ),
                ImageInput(
                    "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6e/Golde33443.jpg/640px-Golde33443.jpg"
                ),
            ],
            backend="cloud",
        )  # Will auto-select vision model

        print(f"Comparison: {response}")

    except Exception as e:
        print(f"Multiple image comparison failed: {e}")

    print()


def streaming_with_vision():
    """Stream a response for image analysis."""
    print("=== Streaming with Vision ===\n")

    try:
        print("Analysis: ", end="", flush=True)
        for chunk in stream(
            [
                "Write a detailed analysis of this image, including colors, composition, and mood. Take your time to describe everything you observe.",
                ImageInput(
                    "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Python-logo-notext.svg/200px-Python-logo-notext.svg.png"
                ),
            ],
            model="gpt-4-vision-preview",
        ):
            print(chunk, end="", flush=True)
        print("\n")

    except Exception as e:
        print(f"Streaming vision failed: {e}")

    print()


def chat_with_images():
    """Use images in a chat session."""
    print("=== Chat with Images ===\n")

    try:
        with chat(model="gpt-4-vision-preview") as session:
            # First message with image
            response1 = session.ask(
                [
                    "Look at this logo and tell me what programming language it represents.",
                    ImageInput(
                        "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Python-logo-notext.svg/200px-Python-logo-notext.svg.png"
                    ),
                ]
            )
            print(f"AI: {response1}")

            # Follow-up without image - AI remembers the previous image
            response2 = session.ask(
                "What are the main design elements and colors in that logo?"
            )
            print(f"AI: {response2}")

            # Another follow-up
            response3 = session.ask("What does the snake symbolize in this context?")
            print(f"AI: {response3}")

    except Exception as e:
        print(f"Chat with images failed: {e}")

    print()


def vision_model_selection():
    """Show different vision models and capabilities."""
    print("=== Vision Model Selection ===\n")

    # Try different vision models
    vision_models = ["gpt-4-vision-preview", "gemini-pro-vision", "claude-3-sonnet"]

    for model in vision_models:
        try:
            response = ask(
                [
                    "Describe this image in one sentence.",
                    ImageInput(
                        "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Python-logo-notext.svg/200px-Python-logo-notext.svg.png"
                    ),
                ],
                model=model,
            )
            print(f"{model}: {response}")
        except Exception as e:
            print(f"{model}: Failed - {e}")

    print()


def handle_backend_errors():
    """Demonstrate handling backend-related errors."""
    print("=== Backend Error Handling ===\n")

    # 1. Backend not available
    try:
        response = ask("Hello", backend="nonexistent")
    except BackendNotAvailableError as e:
        print(f"Backend not available: {e}")
        print(f"  Details: {e.details}")
        print(f"  Available backends: local, cloud")

    # 2. Backend connection error
    try:
        # Save original config
        original_url = os.environ.get("OLLAMA_BASE_URL")

        # Set wrong URL to trigger connection error
        os.environ["OLLAMA_BASE_URL"] = "http://localhost:99999"
        response = ask("Hello", backend="local")

    except BackendConnectionError as e:
        print(f"\nConnection error: {e}")
        print(f"  Backend: {e.details.get('backend', 'unknown')}")
        print(f"  This often means the local server (like Ollama) isn't running")

    except Exception as e:
        print(f"\nConnection issue: {type(e).__name__}: {e}")

    finally:
        # Restore original URL
        if original_url:
            os.environ["OLLAMA_BASE_URL"] = original_url
        else:
            os.environ.pop("OLLAMA_BASE_URL", None)

    print()


def handle_model_errors():
    """Demonstrate handling model-related errors."""
    print("=== Model Error Handling ===\n")

    # 1. Model not found
    try:
        response = ask("Hello", model="nonexistent-model-xyz")
    except ModelNotFoundError as e:
        print(f"Model not found: {e}")
        print(f"  Model: {e.details.get('model', 'unknown')}")
        print(f"  Backend: {e.details.get('backend', 'unknown')}")
        print(f"  Try listing available models first")

    # 2. Multi-modal error (using vision on non-vision model)
    try:
        response = ask(
            ["What's in this image?", ImageInput("https://via.placeholder.com/150")],
            model="gpt-3.5-turbo",  # Non-vision model
        )
    except MultiModalError as e:
        print(f"\nMulti-modal error: {e}")
        print(f"  Reason: {e.details.get('reason', 'Model does not support vision')}")
        print(f"  Solution: Use a vision-capable model like 'gpt-4-vision-preview'")

    except Exception as e:
        print(f"\nModel capability error: {type(e).__name__}: {e}")

    print()


def handle_api_key_errors():
    """Demonstrate handling API key errors."""
    print("=== API Key Error Handling ===\n")

    # Save current API key
    original_key = os.environ.get("OPENAI_API_KEY")

    try:
        # Set invalid API key
        os.environ["OPENAI_API_KEY"] = "invalid-key-123"

        response = ask("Hello", model="gpt-3.5-turbo", backend="cloud")

    except APIKeyError as e:
        print(f"API key error: {e}")
        print(f"  Provider: {e.details.get('provider', 'unknown')}")
        print(f"  Environment variable: {e.details.get('env_var', 'unknown')}")
        print(f"  Solution: Set a valid API key in your environment")

    except Exception as e:
        print(f"Authentication error: {type(e).__name__}: {e}")

    finally:
        # Restore original key
        if original_key:
            os.environ["OPENAI_API_KEY"] = original_key
        else:
            os.environ.pop("OPENAI_API_KEY", None)

    print()


def handle_session_errors():
    """Demonstrate handling session-related errors."""
    print("=== Session Error Handling ===\n")

    # 1. Load non-existent session
    try:
        session = PersistentChatSession.load("nonexistent_session.json")
    except SessionLoadError as e:
        print(f"Session load error: {e}")
        print(f"  File: {e.details.get('file_path', 'unknown')}")
        print(f"  Reason: {e.details.get('reason', 'File not found')}")

    # 2. Save to invalid location
    try:
        with chat(persist=True) as session:
            session.ask("Hello")
            # Try to save to a directory that doesn't exist
            session.save("/nonexistent/directory/session.json")
    except SessionSaveError as e:
        print(f"\nSession save error: {e}")
        print(f"  File: {e.details.get('file_path', 'unknown')}")
        print(f"  Reason: {e.details.get('reason', 'Invalid path')}")

    # 3. Invalid parameters
    try:
        with chat(persist=True) as session:
            session.ask("Test")
            session.save("test.json", format="invalid_format")
    except InvalidParameterError as e:
        print(f"\nInvalid parameter: {e}")
        print(f"  Parameter: {e.details.get('parameter', 'unknown')}")
        print(f"  Value: {e.details.get('value', 'unknown')}")
        print(f"  Valid formats: json, pickle")

    print()


def handle_rate_limit_errors():
    """Demonstrate handling rate limit errors."""
    print("=== Rate Limit Error Handling ===\n")

    print("Rate limit errors occur when making too many requests too quickly.")
    print("Here's how to handle them:")
    print()

    example_code = '''
import time
from matilda_brain import ask, RateLimitError

def robust_ask(prompt, max_retries=3):
    """Ask with automatic retry on rate limits."""
    for attempt in range(max_retries):
        try:
            return ask(prompt)
        except RateLimitError as e:
            if attempt == max_retries - 1:
                raise  # Re-raise on final attempt

            retry_after = e.details.get('retry_after', 60)
            print(f"Rate limited, waiting {retry_after} seconds...")
            time.sleep(retry_after)

# Usage
response = robust_ask("Hello, world!")
'''

    print(example_code)


def production_error_handling():
    """Show production-ready error handling patterns."""
    print("=== Production Error Handling Patterns ===\n")

    def robust_ai_call(prompt, **kwargs):
        """Production-ready AI call with comprehensive error handling."""
        try:
            return ask(prompt, **kwargs)

        except APIKeyError as e:
            print(f"Configuration error: {e}")
            print("Please check your API key configuration")
            return None

        except ModelNotFoundError as e:
            print(f"Model error: {e}")
            print("Falling back to default model...")
            return ask(prompt, model="gpt-3.5-turbo")

        except BackendConnectionError as e:
            print(f"Connection error: {e}")
            print("Trying alternative backend...")
            return ask(prompt, backend="cloud")

        except RateLimitError as e:
            print(f"Rate limit exceeded: {e}")
            retry_after = e.details.get("retry_after", 60)
            print(f"Consider implementing retry logic with {retry_after}s delay")
            return None

        except AIError as e:
            # Catch-all for any other AI library errors
            print(f"AI library error: {type(e).__name__}: {e}")
            return None

        except Exception as e:
            # Unexpected errors
            print(f"Unexpected error: {type(e).__name__}: {e}")
            return None

    # Test the robust function
    print("Testing robust AI call:")
    result = robust_ai_call("What is Python?")
    if result:
        print(f"Success: {result}")
    else:
        print("Call failed gracefully")

    print()


def config_error_handling():
    """Show configuration error handling."""
    print("=== Configuration Error Handling ===\n")

    # Create an invalid config file
    invalid_config = Path("invalid_config.yaml")
    invalid_config.write_text("invalid: yaml: content: [}")

    try:
        from matilda_brain.config import load_config

        config = load_config(invalid_config)

    except ConfigFileError as e:
        print(f"Config file error: {e}")
        print(f"  File: {e.details.get('file_path', 'unknown')}")
        print(f"  Reason: {e.details.get('reason', 'Invalid format')}")
        print(f"  Solution: Check your YAML syntax")

    except Exception as e:
        print(f"Configuration error: {type(e).__name__}: {e}")

    finally:
        # Clean up
        if invalid_config.exists():
            invalid_config.unlink()

    print()


def best_practices():
    """Show best practices for advanced usage."""
    print("=== Best Practices ===\n")

    print("1. Always handle specific exceptions first:")
    print(
        """
try:
    response = ask(prompt, model=user_model)
except ModelNotFoundError:
    # Handle model not found
    response = ask(prompt)  # Use default model
except APIKeyError as e:
    # Handle API key issues
    env_var = e.details.get('env_var')
    print(f"Please set {env_var} environment variable")
except AIError as e:
    # Catch-all for AI library errors
    logger.error(f"AI operation failed: {e}")
"""
    )

    print("\n2. Use context managers for sessions:")
    print(
        """
with chat(persist=True) as session:
    # Session is automatically saved/cleaned up
    response = session.ask("Hello")
"""
    )

    print("\n3. Implement retry logic for production:")
    print(
        """
import time
from matilda_brain import RateLimitError

def ask_with_retry(prompt, max_retries=3):
    for attempt in range(max_retries):
        try:
            return ask(prompt)
        except RateLimitError as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(e.details.get('retry_after', 60))
"""
    )

    print("\n4. Check response success:")
    print(
        """
response = ask("Hello")
if response.failed:
    print(f"Request failed: {response.error}")
    # Handle failure
else:
    print(f"Success: {response}")
"""
    )

    print()


def main():
    """Run all advanced examples."""
    print("Matilda Brain - Advanced Features Examples")
    print("=" * 50)
    print()
    print("This example shows advanced features including multi-modal AI,")
    print("comprehensive error handling, and production-ready patterns.")
    print()

    # Multi-modal examples
    print("🖼️  MULTI-MODAL EXAMPLES")
    print("-" * 30)
    basic_image_analysis()
    multiple_images_comparison()
    streaming_with_vision()
    chat_with_images()
    vision_model_selection()

    # Error handling examples
    print("🚨 ERROR HANDLING EXAMPLES")
    print("-" * 30)
    handle_backend_errors()
    handle_model_errors()
    handle_api_key_errors()
    handle_session_errors()
    handle_rate_limit_errors()
    production_error_handling()
    config_error_handling()
    best_practices()

    print("=" * 50)
    print("Advanced Features Examples Complete!")
    print()
    print("Key takeaways:")
    print("- Multi-modal AI enables vision capabilities")
    print("- Specific exception handling improves reliability")
    print("- Production code should handle all error types")
    print("- Use context managers for resource management")
    print("- Implement retry logic for rate limits")
    print("- Always check response success in production")
    print()
    print("You've now seen all the core features of the AI library!")
    print("Check the plugins/ directory for extension examples.")


if __name__ == "__main__":
    main()
