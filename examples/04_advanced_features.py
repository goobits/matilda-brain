#!/usr/bin/env python3
"""Async, multimodal, runtime configuration, and error-handling examples."""

import asyncio
from pathlib import Path

from matilda_brain import AIError, ImageInput, RateLimitError, ask, ask_async, configure, stream_async


def analyze_image(path: Path) -> None:
    response = ask(
        ["Describe this image and identify any visible text", ImageInput(path)],
        model="openai/gpt-4o",
    )
    print(response)


async def main() -> None:
    configure(default_backend="cloud", timeout=60)

    try:
        print(await ask_async("Explain async context managers", model="@fast"))
        async for chunk in stream_async("Give one practical asyncio tip", model="@fast"):
            print(chunk, end="", flush=True)
        print()
    except RateLimitError as error:
        print(f"Provider rate limited the request: {error}")
    except AIError as error:
        print(f"Brain request failed: {error}")


if __name__ == "__main__":
    asyncio.run(main())
