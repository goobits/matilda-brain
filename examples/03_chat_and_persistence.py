#!/usr/bin/env python3
"""Save, load, summarize, and export a conversation."""

from pathlib import Path

from matilda_brain import PersistentChatSession, chat

SESSION_PATH = Path(".artifacts/examples/brain-session.json")


def main() -> None:
    SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    with chat(system="Keep project notes concise", model="@fast") as session:
        session.ask("The release codename is Aurora.")
        session.ask("Summarize the release note.")
        session.save(SESSION_PATH)
        print(session.get_summary())

    restored = PersistentChatSession.load(SESSION_PATH)
    try:
        print(restored.ask("What is the release codename?"))
        print(restored.export_messages("markdown"))
    finally:
        restored.close()

    print(f"Saved session: {SESSION_PATH.resolve()}")


if __name__ == "__main__":
    main()
