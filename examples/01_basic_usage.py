#!/usr/bin/env python3
"""Core request, streaming, and conversation examples."""

from matilda_brain import ask, chat, stream


def main() -> None:
    response = ask("Explain Python context managers in three sentences", model="@fast")
    print(response)
    print(f"\nmodel={response.model} backend={response.backend} time={response.time_taken}")

    print("\nStreaming:")
    for chunk in stream("Write a two-line poem about clean code", model="@fast"):
        print(chunk, end="", flush=True)
    print()

    print("\nConversation:")
    with chat(system="Answer briefly", model="@fast") as session:
        print(session.ask("Remember that my project is named Matilda."))
        print(session.ask("What is my project named?"))


if __name__ == "__main__":
    main()
