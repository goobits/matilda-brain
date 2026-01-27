import asyncio
import sys
import time
import os
from unittest.mock import MagicMock

# Add src to sys.path to import matilda_brain
sys.path.insert(0, os.path.abspath("src"))

# Mock matilda_transport
mock_transport = MagicMock()
sys.modules["matilda_transport"] = mock_transport

from matilda_brain.tools.builtins.code import run_python

async def background_task():
    """A task that should run concurrently."""
    print("Background task started")
    last_time = time.time()
    for i in range(10):
        now = time.time()
        # print(f"Background task heartbeat {i} (delta: {now - last_time:.2f}s)")
        # If delta is large (> 0.6s), it means we were blocked
        if now - last_time > 1.0:
            print(f"BLOCKED! Heartbeat delayed by {now - last_time:.2f}s")
        else:
            print(f"Background task heartbeat {i}")

        last_time = now
        await asyncio.sleep(0.2)
    print("Background task finished")

async def main():
    print("Starting reproduction script...")

    # Python code that sleeps for 2 seconds
    python_code = """
import time
print("Code started")
time.sleep(2)
print("Code finished")
"""

    # Start background task
    bg_task = asyncio.create_task(background_task())

    # Give background task a moment to start
    await asyncio.sleep(0.1)

    print("Calling run_python...")
    start_time = time.time()

    # Determine if run_python is async or sync wrapper
    if asyncio.iscoroutinefunction(run_python):
        print("run_python is async")
        result = await run_python(code=python_code)
    else:
        print("run_python is sync")
        result = run_python(code=python_code)

    end_time = time.time()
    print(f"run_python returned in {end_time - start_time:.2f}s")
    print(f"Result: {result.strip()}")

    await bg_task

if __name__ == "__main__":
    asyncio.run(main())
