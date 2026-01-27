import asyncio
import time
import urllib.request
import urllib.parse
import json
import threading
import sys
from unittest.mock import MagicMock

# --- Mock missing dependency ---
sys.modules["matilda_transport"] = MagicMock()

from aiohttp import web
from matilda_brain.tools.builtins.web import http_request

# --- Local Server Setup ---
async def handle_delay(request):
    try:
        delay = float(request.match_info.get('seconds', 0))
    except ValueError:
        delay = 0
    await asyncio.sleep(delay)
    return web.Response(text=f"Delayed by {delay}s")

async def start_server():
    app = web.Application()
    app.router.add_get('/delay/{seconds}', handle_delay)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    return site, runner

# --- Blocking Implementation (Simulation of "Before") ---
def blocking_http_request(url, timeout=10):
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode("utf-8")
    except Exception as e:
        return str(e)

# --- Benchmark Logic ---
async def benchmark():
    # Start server
    site, runner = await start_server()
    port = site._server.sockets[0].getsockname()[1]
    base_url = f"http://127.0.0.1:{port}"
    print(f"Server started on {base_url}")

    delay = 1.0
    count = 3
    url = f"{base_url}/delay/{delay}"

    print(f"\nRunning benchmark with {count} concurrent requests, each taking {delay}s...")

    # 1. Blocking Benchmark
    print("\n--- Blocking Implementation ---")

    async def wrapper_blocking():
        blocking_http_request(url)

    t0 = time.time()
    await asyncio.gather(*[wrapper_blocking() for _ in range(count)])
    t1 = time.time()
    blocking_duration = t1 - t0
    print(f"Total time (Blocking): {blocking_duration:.2f}s")
    print(f"Expected time if blocking: ~{count * delay}s")

    # 2. Async Implementation
    print("\n--- Async Implementation ---")

    # The actual tool
    async def wrapper_async():
        res = await http_request(url)
        return res

    t0 = time.time()
    results = await asyncio.gather(*[wrapper_async() for _ in range(count)])
    t1 = time.time()
    async_duration = t1 - t0
    print(f"Total time (Async): {async_duration:.2f}s")
    print(f"Expected time if non-blocking: ~{delay}s")
    print(f"Sample Result: {results[0]}")

    # Cleanup
    await runner.cleanup()

    return blocking_duration, async_duration

if __name__ == "__main__":
    blocking_time, async_time = asyncio.run(benchmark())

    if async_time < blocking_time / 2 and async_time > 0.5:
        print("\n✅ SUCCESS: Async implementation is significantly faster (non-blocking).")
    else:
        print("\n❌ FAILURE: Async implementation is not significantly faster or failed.")
