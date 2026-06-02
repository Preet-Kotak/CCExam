import asyncio
import http.server
import os
import threading
from typing import Optional
import aiohttp

RENDER_URL: str = os.environ.get("RENDER_URL", "")
KEEPALIVE_INTERVAL: int = int(os.environ.get("KEEPALIVE_INTERVAL", "300"))

def start_http_server_sync(port: int) -> None:
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot is alive!")

        def log_message(self, *args) -> None:
            pass

    server = http.server.HTTPServer(("0.0.0.0", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[HTTP] Server started on port {port}")


async def self_ping() -> None:
    if not RENDER_URL:
        print("[Keepalive] RENDER_URL not set — self-ping disabled.")
        return
    await asyncio.sleep(30)
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(
                    f"{RENDER_URL}/health",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    print(f"[Keepalive] Ping → {resp.status}")
            except Exception as exc:
                print(f"[Keepalive] Ping failed: {exc}")
            await asyncio.sleep(KEEPALIVE_INTERVAL)