#!/usr/bin/env python3
"""
Chat and persistence examples for the AI library.

This script demonstrates advanced chat session functionality including:
- Persistent chat sessions
- Saving and loading conversations
- Multi-session management
- Chat with tools
- Cost tracking and session management
"""

from pathlib import Path

import matilda_brain
from matilda_brain import PersistentChatSession, chat
from matilda_brain.tools import tool


def basic_chat_examples():
    """Basic chat session examples."""
    print("=== Basic Chat Sessions ===\n")

    print("1. Simple conversation:")
    with chat() as session:
        response1 = session.ask("Hi, I'm learning Python programming")
        print(f"User: Hi, I'm learning Python programming")
        print(f"AI: {response1}")

        response2 = session.ask("What should I learn first?")
        print(f"User: What should I learn first?")
        print(f"AI: {response2}")

        response3 = session.ask("Can you give me a simple example?")
        print(f"User: Can you give me a simple example?")
        print(f"AI: {response3}")

    print()

    print("2. Chat with system prompt:")
    with chat(
        system="You are an expert Python tutor who gives concise, practical answers"
    ) as tutor:
        response = tutor.ask("How do I create a dictionary in Python?")
        print(f"User: How do I create a dictionary in Python?")
        print(f"Tutor: {response}")

    print()


def basic_persistence():
    """Basic save and load example."""
    print("=== Basic Persistence ===\n")

    # Create a persistent session
    with ttt.chat(persist=True, system="You are a helpful coding assistant") as session:
        # Have a conversation
        session.ask("My name is Alice and I'm learning web development.")
        session.ask("I want to build a portfolio website.")
        session.ask("Should I use React or Vue?")

        # Save the session
        session.save("alice_coding_session.json")
        print("Session saved to alice_coding_session.json")

        # Get session summary
        summary = session.get_summary()
        print(f"Messages: {summary['message_count']}")
        print(f"Duration: {summary['duration']}")

    # Load and resume the session
    print("\nLoading saved session...")
    session = PersistentChatSession.load("alice_coding_session.json")

    # Continue the conversation
    response = session.ask("What's my name and what am I building?")
    print(f"User: What's my name and what am I building?")
    print(f"AI: {response}")

    # Clean up
    Path("alice_coding_session.json").unlink()


def advanced_session_management():
    """Advanced session management features."""
    print("\n=== Advanced Session Management ===\n")

    # Create session with custom ID
    session = PersistentChatSession(
        session_id="project_manager_001",
        system="You are a project management assistant specialized in software development",
    )

    # Build conversation
    session.ask("I need to plan a web application project")
    session.ask(
        "The app should have user authentication, a dashboard, and data visualization"
    )
    session.ask("We have 2 developers and 8 weeks")

    # Save in different formats
    session.save("project_plan.json", format="json")
    session.save("project_plan.pkl", format="pickle")
    print("Session saved in both JSON and pickle formats")

    # Export conversation
    print("\nConversation export (Markdown):")
    print(session.export_messages(format="markdown"))

    # Get detailed summary
    summary = session.get_summary()
    print(f"\nSession Summary:")
    print(f"  ID: {summary['session_id']}")
    print(f"  Messages: {summary['message_count']}")
    print(
        f"  Tokens used: {summary['total_tokens_in']} in, {summary['total_tokens_out']} out"
    )
    print(f"  Estimated cost: ${summary['total_cost']:.4f}")

    # Clean up
    Path("project_plan.json").unlink()
    Path("project_plan.pkl").unlink()


def multi_session_tracking():
    """Track multiple sessions for different purposes."""
    print("\n=== Multi-Session Tracking ===\n")

    sessions_dir = Path("chat_sessions")
    sessions_dir.mkdir(exist_ok=True)

    # Create different sessions for different purposes
    sessions = {
        "coding": PersistentChatSession(
            system="You are an expert Python developer", session_id="coding_helper"
        ),
        "learning": PersistentChatSession(
            system="You are a patient teacher who explains concepts clearly",
            session_id="learning_helper",
        ),
        "planning": PersistentChatSession(
            system="You are a strategic thinking partner", session_id="planning_helper"
        ),
    }

    # Use different sessions
    sessions["coding"].ask("How do I implement a binary search algorithm?")
    sessions["learning"].ask("Explain machine learning concepts for a beginner")
    sessions["planning"].ask("Help me plan a career transition into tech")

    # Save all sessions
    for name, session in sessions.items():
        path = sessions_dir / f"{name}_session.json"
        session.save(path)
        print(f"Saved {name} session to {path}")

    # Load and display summaries
    print("\nSession Summaries:")
    for name in sessions:
        path = sessions_dir / f"{name}_session.json"
        loaded_session = PersistentChatSession.load(path)
        summary = loaded_session.get_summary()
        print(
            f"  {name}: {summary['message_count']} messages, {summary['total_tokens_in']} tokens"
        )

    # Clean up
    import shutil

    shutil.rmtree(sessions_dir)


def incremental_conversation():
    """Build a conversation incrementally across runs."""
    print("\n=== Incremental Conversation ===\n")

    session_file = Path("learning_progress.json")

    # Load existing session or create new one
    if session_file.exists():
        print("Resuming existing learning session...")
        session = PersistentChatSession.load(session_file)
        print(f"Loaded {len(session.history)} previous messages")
    else:
        print("Starting new learning session...")
        session = PersistentChatSession(
            system="You are a coding tutor who tracks student progress",
            session_id="python_learning",
        )

    # Learning topics to cover
    topics = [
        "What are the basic data types in Python?",
        "How do I work with lists and dictionaries?",
        "Explain functions and parameters",
        "What are classes and objects?",
        "How do I handle errors with try/except?",
    ]

    # Pick next topic based on conversation length
    user_messages = [m for m in session.history if m["role"] == "user"]
    topic_index = len(user_messages)

    if topic_index < len(topics):
        response = session.ask(topics[topic_index])
        print(f"\nTopic {topic_index + 1}: {topics[topic_index]}")
        print(f"Answer: {response}")

        # Save progress
        session.save(session_file)
        print(
            f"\nProgress saved. Run again to continue learning! ({len(topics) - topic_index - 1} topics remaining)"
        )
    else:
        print("\nAll topics covered! Here's your learning journey:")
        print(session.export_messages(format="text"))

        # Clean up completed session
        session_file.unlink()
        print("\nLearning session completed!")


# Define tools for chat with tools examples
@tool
def get_weather(city: str) -> str:
    """Get current weather for a city."""
    weather_data = {
        "New York": "72°F, Sunny",
        "London": "60°F, Cloudy",
        "Tokyo": "68°F, Clear",
        "Paris": "65°F, Partly Cloudy",
    }
    return weather_data.get(city, f"Weather data not available for {city}")


@tool
def calculate(expression: str) -> str:
    """Calculate mathematical expressions."""
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"Calculation error: {e}"


def persistent_chat_with_tools():
    """Persistent chat session with tools."""
    print("\n=== Persistent Chat with Tools ===\n")

    # Create persistent session with tools
    session = PersistentChatSession(
        system="You are a helpful assistant with access to weather and calculation tools.",
        tools=[get_weather, calculate],
        session_id="weather_calc_assistant",
    )

    # First conversation
    print(f"Session ID: {session.session_id}")

    response1 = session.ask("What's the weather like in London?")
    print(f"User: What's the weather like in London?")
    print(f"Assistant: {response1}")

    response2 = session.ask("If it's 60°F there, what's that in Celsius?")
    print(f"\nUser: If it's 60°F there, what's that in Celsius?")
    print(f"Assistant: {response2}")

    # Save session
    save_path = "weather_assistant.json"
    session.save(save_path)
    print(f"\nSession saved to {save_path}")

    # Load session and continue
    loaded_session = PersistentChatSession.load(save_path)
    print(f"\nLoaded session with {len(loaded_session.history)} messages")

    # Continue conversation
    response3 = loaded_session.ask("What about Tokyo's weather?")
    print(f"User: What about Tokyo's weather?")
    print(f"Assistant: {response3}")

    # Show tool usage statistics
    print(f"\nTool usage statistics:")
    if hasattr(loaded_session, "metadata") and "tools_used" in loaded_session.metadata:
        for tool_name, count in loaded_session.metadata["tools_used"].items():
            print(f"  - {tool_name}: {count} calls")

    # Clean up
    Path(save_path).unlink()


def session_with_multimodal():
    """Persistent session with multi-modal content."""
    print("\n=== Session with Multi-modal Content ===\n")

    try:
        with ttt.chat(persist=True, model="gpt-4-vision-preview") as session:
            # First interaction with image
            session.ask(
                [
                    "I'm going to show you images for analysis.",
                    "Here's a Python logo:",
                    ttt.ImageInput(
                        "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Python-logo-notext.svg/200px-Python-logo-notext.svg.png"
                    ),
                ]
            )

            # Follow-up without image
            response = session.ask(
                "What programming language does this logo represent?"
            )
            print(f"User: What programming language does this logo represent?")
            print(f"AI: {response}")

            # Save the multi-modal session
            session.save("multimodal_session.json")
            print("\nMulti-modal session saved!")

        # Load and continue
        loaded = PersistentChatSession.load("multimodal_session.json")
        response = loaded.ask("What are the main colors in that logo?")
        print(f"\nUser: What are the main colors in that logo?")
        print(f"AI: {response}")

        # Clean up
        Path("multimodal_session.json").unlink()

    except Exception as e:
        print(f"Multi-modal example requires vision model: {e}")


def cost_tracking_example():
    """Track costs and usage across sessions."""
    print("\n=== Cost Tracking ===\n")

    # Create a session for cost tracking
    with ttt.chat(persist=True, model="gpt-3.5-turbo") as session:
        # Simulate some API calls
        session.ask("Explain Python list comprehensions")
        session.ask("Give me 3 examples")
        session.ask("What are the performance benefits?")

        # Get cost summary
        summary = session.get_summary()
        print(f"Session Cost Summary:")
        print(f"  Total tokens in: {summary['total_tokens_in']}")
        print(f"  Total tokens out: {summary['total_tokens_out']}")
        print(f"  Estimated cost: ${summary['total_cost']:.4f}")

        # Model usage breakdown
        if "model_usage" in summary:
            print(f"\nModel Usage:")
            for model, usage in summary["model_usage"].items():
                print(f"  {model}:")
                print(f"    Calls: {usage['count']}")
                print(f"    Tokens: {usage['tokens_in']} in, {usage['tokens_out']} out")
                print(f"    Cost: ${usage['cost']:.4f}")

        # Save for record keeping
        session.save("usage_report.json")
        print("\nSession saved for record keeping")

    # Clean up
    Path("usage_report.json").unlink()


def main():
    """Run all examples."""
    print("AI Library - Chat and Persistence Examples")
    print("=" * 50)
    print()
    print("This example shows advanced chat features including persistence,")
    print("multi-session management, and chat with tools.")
    print()

    try:
        basic_chat_examples()
        basic_persistence()
        advanced_session_management()
        multi_session_tracking()
        incremental_conversation()
        persistent_chat_with_tools()
        session_with_multimodal()
        cost_tracking_example()

        print("\n" + "=" * 50)
        print("Chat and Persistence Examples Complete!")
        print()
        print("Key takeaways:")
        print("- Chat sessions maintain conversation context")
        print("- Persistent sessions can be saved and loaded")
        print("- Multiple sessions can be managed for different purposes")
        print("- Tools work seamlessly within chat sessions")
        print("- Sessions track usage and costs automatically")
        print("- Multi-modal content is preserved in sessions")
        print()
        print("Next steps:")
        print("- Try 04_advanced_features.py for multi-modal and production features")

    except Exception as e:
        print(f"\nError running examples: {e}")
        print("Make sure you have API keys configured for cloud models.")


if __name__ == "__main__":
    main()
