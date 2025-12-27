#!/usr/bin/env python3
"""
Tools and workflows examples for the AI library.

This script demonstrates how to use the comprehensive set of built-in tools
and create custom tools for complex workflows.
"""

import asyncio

from ai import ask, chat

from matilda_brain.tools import get_tool, list_tools, tool
from matilda_brain.tools.builtins import (
    calculate,
    get_current_time,
    http_request,
    list_directory,
    read_file,
    run_python,
    web_search,
    write_file,
)


def demo_tool_discovery():
    """Show how to discover available tools."""
    print("=== Tool Discovery ===\n")

    # List all tools
    all_tools = list_tools()
    print(f"Total available tools: {len(all_tools)}")

    # Group by category
    categories = {}
    for tool in all_tools:
        if tool.category not in categories:
            categories[tool.category] = []
        categories[tool.category].append(tool.name)

    print("\nTools by category:")
    for category, tools in sorted(categories.items()):
        print(f"  {category}: {', '.join(tools)}")

    # Get specific tool info
    print("\n=== Tool Details ===")
    calc_tool = get_tool("calculate")
    if calc_tool:
        print(f"Name: {calc_tool.name}")
        print(f"Description: {calc_tool.description}")
        print(f"Parameters:")
        for param in calc_tool.parameters:
            print(f"  - {param.name} ({param.type.value}): {param.description}")


def demo_file_operations():
    """Demonstrate file operation tools."""
    print("\n=== File Operations Demo ===\n")

    # List current directory
    print("1. Listing Python files:")
    response = ask(
        "List all Python files in the current directory", tools=["list_directory"]
    )
    print(f"Response: {response.response}")

    # Create a test file
    print("\n2. Creating a test file:")
    response = ask(
        "Create a file called 'test_output.txt' with the content 'Hello from AI tools!'",
        tools=["write_file"],
    )
    print(f"Response: {response.response}")

    # Read the file back
    print("\n3. Reading the file:")
    response = ask("Read the contents of test_output.txt", tools=["read_file"])
    print(f"Response: {response.response}")


def demo_web_and_calculation():
    """Demonstrate web search and calculation tools."""
    print("\n=== Web Search & Calculation Demo ===\n")

    # Search and calculate
    response = ask(
        "Search for the distance from Earth to Mars in kilometers, "
        "then calculate how long it would take to travel there at 50,000 km/h",
        tools=["web_search", "calculate"],
    )
    print(f"Response: {response.response}")

    if response.tools_called:
        print("\nTools used:")
        for call in response.tool_calls:
            print(f"  - {call.name}: {'Success' if call.succeeded else 'Failed'}")


def demo_time_operations():
    """Demonstrate time-related tools."""
    print("\n=== Time Operations Demo ===\n")

    response = ask(
        "What time is it right now in Tokyo, London, and New York? "
        "Show me in 24-hour format.",
        tools=["get_current_time"],
    )
    print(f"Response: {response.response}")


def demo_code_execution():
    """Demonstrate safe code execution."""
    print("\n=== Code Execution Demo ===\n")

    response = ask(
        "Write and run a Python script that generates the first 10 Fibonacci numbers",
        tools=["run_python"],
    )
    print(f"Response: {response.response}")

    if response.tools_called:
        for call in response.tool_calls:
            if call.name == "run_python" and call.succeeded:
                print(f"\nCode output:\n{call.result}")


def demo_api_requests():
    """Demonstrate HTTP API requests."""
    print("\n=== API Request Demo ===\n")

    # Get public API data
    response = ask(
        "Make a request to https://api.github.com/users/python and tell me about the Python organization",
        tools=["http_request"],
    )
    print(f"Response: {response.response}")


def demo_complex_workflow():
    """Demonstrate a complex multi-tool workflow."""
    print("\n=== Complex Workflow Demo ===\n")

    response = ask(
        "Search for information about Python list comprehensions, "
        "create a Python example that demonstrates them, "
        "save it to 'list_comp_demo.py', "
        "and then run it to show the output",
        tools=["web_search", "write_file", "run_python"],
    )

    print(f"Response: {response.response}")

    if response.tools_called:
        print("\nWorkflow steps:")
        for i, call in enumerate(response.tool_calls, 1):
            status = "✓" if call.succeeded else "✗"
            print(f"  {i}. {status} {call.name}")
            if not call.succeeded:
                print(f"     Error: {call.error}")


# Define custom tools for chat examples
@tool
def get_weather(city: str) -> str:
    """Get the current weather for a city.

    Args:
        city: The city name to get weather for
    """
    # In a real implementation, this would call a weather API
    weather_data = {
        "New York": "72°F, Sunny",
        "London": "60°F, Cloudy",
        "Tokyo": "68°F, Clear",
        "Sydney": "75°F, Partly Cloudy",
    }
    return weather_data.get(city, f"Unknown weather for {city}")


@tool
def calculate_math(expression: str) -> str:
    """Evaluate a mathematical expression.

    Args:
        expression: Mathematical expression to evaluate
    """
    try:
        # Note: eval() is dangerous in production! Use a proper math parser
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"Error: {e}"


def demo_chat_with_tools():
    """Demonstrate chat sessions with custom tools."""
    print("\n=== Chat with Custom Tools ===\n")

    # Create a chat session with custom tools
    with chat(tools=[get_weather, calculate_math]) as session:
        # Ask about weather
        response = session.ask("What's the weather in New York?")
        print(f"User: What's the weather in New York?")
        print(f"Assistant: {response}")

        # Ask for calculation
        response = session.ask("Calculate 15 * 23 + 42")
        print(f"\nUser: Calculate 15 * 23 + 42")
        print(f"Assistant: {response}")

        # Ask for something requiring both tools
        response = session.ask(
            "What's the weather in Tokyo, and if it's 68°F, what's that in Celsius?"
        )
        print(
            f"\nUser: What's the weather in Tokyo, and if it's 68°F, what's that in Celsius?"
        )
        print(f"Assistant: {response}")


def demo_builtin_tools_in_chat():
    """Demonstrate built-in tools in chat sessions."""
    print("\n=== Chat with Built-in Tools ===\n")

    with chat(tools=["web_search", "calculate", "write_file"]) as session:
        response = session.ask(
            "Search for the current population of Japan, then calculate how many "
            "people that would be per square kilometer if Japan is 377,975 km². "
            "Save the result to a file called 'japan_stats.txt'"
        )
        print(f"User: [Complex request about Japan population and density]")
        print(f"Assistant: {response}")

        # Check what tools were used
        if hasattr(response, "tool_calls") and response.tool_calls:
            print("\nTools used in this conversation:")
            for call in response.tool_calls:
                print(f"  - {call.name}: {'Success' if call.succeeded else 'Failed'}")


def demo_cli_examples():
    """Show CLI examples with tools."""
    print("\n=== CLI Tool Examples ===\n")
    print("You can use tools from the command line in several ways:")
    print()

    print("1. Using built-in tools:")
    print('   ttt "Search for Python tutorials" --tools "web_search"')
    print('   ttt "Calculate 15% of 250" --tools "calculate"')
    print()

    print("2. Using multiple tools:")
    print(
        '   ttt "Search for weather data and calculate averages" --tools "web_search,calculate"'
    )
    print()

    print("3. Using custom tools from modules:")
    print('   ttt "Get system info" --tools "os:getcwd,platform:system"')
    print()

    print("4. Using tools from custom scripts:")
    print('   ttt "Process data" --tools "/path/to/my_tools.py:process_data"')
    print()

    print("5. Complex workflows:")
    print(
        '   ttt "Research topic, analyze data, create report" --tools "web_search,calculate,write_file"'
    )


def main():
    """Run all demonstrations."""
    print("AI Library - Tools and Workflows Examples")
    print("=" * 50)
    print()
    print("This example shows how to use built-in tools and create custom tools.")
    print("Tools enable AI to perform actions and access external data.")
    print()

    # Show available tools
    demo_tool_discovery()

    # Demonstrate each category of tools
    demos = [
        demo_file_operations,
        demo_web_and_calculation,
        demo_time_operations,
        demo_code_execution,
        demo_api_requests,
        demo_complex_workflow,
        demo_chat_with_tools,
        demo_builtin_tools_in_chat,
        demo_cli_examples,
    ]

    for demo in demos:
        try:
            demo()
        except Exception as e:
            print(f"\nError in {demo.__name__}: {e}")

    print("\n" + "=" * 50)
    print("Tools and Workflows Examples Complete!")
    print()
    print("Key takeaways:")
    print("- Tools extend AI capabilities with external actions")
    print("- Built-in tools cover common tasks (web, files, math, code)")
    print("- Custom tools can be created with the @tool decorator")
    print("- Tools work seamlessly in both ask() and chat() contexts")
    print("- Complex workflows can chain multiple tools together")
    print()
    print("Next steps:")
    print("- Try 03_chat_and_persistence.py for advanced chat features")
    print("- Try 04_advanced_features.py for multi-modal and production features")

    # Cleanup
    import os

    for file in ["test_output.txt", "list_comp_demo.py", "japan_stats.txt"]:
        if os.path.exists(file):
            os.remove(file)
            print(f"Cleaned up: {file}")


if __name__ == "__main__":
    main()
