#!/usr/bin/env python3
"""Built-in and custom tool examples."""

from matilda_brain import ask, chat
from matilda_brain.tools import list_tools, tool
from matilda_brain.tools.builtins import calculate, get_current_time


@tool(category="weather")
def get_weather(city: str) -> str:
    """Return example weather data for a city."""
    return f"{city}: sunny, 22 C"


def main() -> None:
    print("Registered tools:", ", ".join(tool.name for tool in list_tools()))

    response = ask(
        "What time is it in UTC, and what is 17 * 23?",
        tools=[get_current_time, calculate],
    )
    print(response)

    with chat(tools=[get_weather, calculate]) as session:
        print(session.ask("What is the weather in Seattle?"))
        print(session.ask("Convert 22 Celsius to Fahrenheit."))


if __name__ == "__main__":
    main()
