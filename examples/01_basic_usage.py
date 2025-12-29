#!/usr/bin/env python3
"""
Basic usage examples for the AI library.

This script demonstrates the core functionality of the unified AI library,
showing how to use the ask(), stream(), and basic chat() functions.

This is the perfect starting point for learning the library.
"""

from matilda_brain import ask, chat, stream


def basic_ask_examples():
    """Demonstrate basic ask() functionality."""
    print("=== Basic Ask Examples ===\n")

    # Simple question
    print("1. Simple question:")
    response = ask("What is Python?")
    print(f"Response: {response}")
    print(f"Model used: {response.model}")
    print(f"Time taken: {response.time:.2f}s")
    print()

    # With system prompt
    print("2. With system prompt:")
    response = ask(
        "Explain recursion",
        system="You are a computer science teacher explaining to beginners",
    )
    print(f"Response: {response}")
    print()

    # Speed preference
    print("3. Prefer speed:")
    response = ask("What's 2+2?", model="gpt-3.5-turbo")
    print(f"Quick answer: {response}")
    print(f"Model: {response.model} (optimized for speed)")
    print()

    # Quality preference
    print("4. Prefer quality:")
    response = ask(
        "Analyze the philosophical implications of artificial intelligence",
        model="gpt-4",
    )
    print(f"Detailed response: {response[:100]}...")
    print(f"Model: {response.model} (optimized for quality)")
    print()


def streaming_examples():
    """Demonstrate streaming functionality."""
    print("=== Streaming Examples ===\n")

    print("1. Streaming story:")
    print("AI: ", end="", flush=True)

    for chunk in stream("Tell me a short story about a friendly robot"):
        print(chunk, end="", flush=True)

    print("\n")

    print("2. Streaming with preferences:")
    print("AI (fast mode): ", end="", flush=True)

    for chunk in stream(
        "Explain machine learning in simple terms", model="gpt-3.5-turbo"
    ):
        print(chunk, end="", flush=True)

    print("\n\n")


def basic_chat_examples():
    """Demonstrate basic chat session functionality."""
    print("=== Basic Chat Examples ===\n")

    print("1. Simple conversation:")
    with chat() as session:
        response1 = session.ask("Hi, I'm learning to code")
        print(f"User: Hi, I'm learning to code")
        print(f"AI: {response1}")

        response2 = session.ask("What language should I start with?")
        print(f"User: What language should I start with?")
        print(f"AI: {response2}")

        response3 = session.ask("Why that one?")
        print(f"User: Why that one?")
        print(f"AI: {response3}")

    print()

    print("2. Chat with system prompt:")
    with chat(system="You are a helpful Python tutor") as tutor:
        response1 = tutor.ask("I'm new to Python")
        print(f"User: I'm new to Python")
        print(f"Tutor: {response1}")

        response2 = tutor.ask("What are lists?")
        print(f"User: What are lists?")
        print(f"Tutor: {response2}")

    print()


def model_selection_examples():
    """Demonstrate explicit model selection."""
    print("=== Model Selection Examples ===\n")

    # Try different backends
    try:
        print("1. Using local backend:")
        response = ask("Hello!", backend="local")
        print(f"Local response: {response}")
        print(f"Backend: {response.backend}")
    except Exception as e:
        print(f"Local backend not available: {e}")

    print()

    try:
        print("2. Using cloud backend:")
        response = ask("Hello!", backend="cloud")
        print(f"Cloud response: {response}")
        print(f"Backend: {response.backend}")
    except Exception as e:
        print(f"Cloud backend not available: {e}")

    print()

    # Smart routing based on query type
    print("3. Smart routing examples:")

    # Code query (should prefer coding models)
    code_response = ask("Write a Python function to calculate fibonacci numbers")
    print(f"Code query model: {code_response.model}")

    # Math query
    math_response = ask("What's 15% of 250?")
    print(f"Math query model: {math_response.model}")

    # Complex analysis
    analysis_response = ask(
        "Provide a comprehensive analysis of renewable energy trends"
    )
    print(f"Analysis query model: {analysis_response.model}")

    print()


def error_handling_examples():
    """Demonstrate basic error handling."""
    print("=== Error Handling Examples ===\n")

    # Example with non-existent model (this will fallback)
    try:
        response = ask("Hello", model="non-existent-model")
        if response.failed:
            print(f"Request failed: {response.error}")
        else:
            print(f"Fallback worked: {response}")
            print(f"Actually used model: {response.model}")
    except Exception as e:
        print(f"Exception occurred: {e}")

    print()


def main():
    """Run all examples."""
    print("Matilda Brain - Basic Usage Examples")
    print("=" * 50)
    print()
    print(
        "This example shows the core functionality: ask(), stream(), and basic chat()"
    )
    print("For more advanced features, see the other numbered examples.")
    print()

    try:
        basic_ask_examples()
        streaming_examples()
        basic_chat_examples()
        model_selection_examples()
        error_handling_examples()

        print("=== Basic Examples Complete ===")
        print("\nNext steps:")
        print("- Try 02_tools_and_workflows.py for built-in tools")
        print("- Try 03_chat_and_persistence.py for advanced chat features")
        print("- Try 04_advanced_features.py for multi-modal and production features")

    except KeyboardInterrupt:
        print("\n\nExamples interrupted by user.")
    except Exception as e:
        print(f"\nError running examples: {e}")
        print(
            "Make sure you have either Ollama running locally or cloud API keys configured."
        )


if __name__ == "__main__":
    main()
