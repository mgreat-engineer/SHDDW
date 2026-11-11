import asyncio
import json
import subprocess
import sys
import time

import websockets

API = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0]
tok = subprocess.check_output([sys.executable, "/app/tests/clerk_token.py", "shadow.a+clerk_test@example.com"]).decode().strip()


async def main():
    url = API.replace("https://", "wss://") + f"/api/browser/stream?token={tok}&group=1"
    async with websockets.connect(url, max_size=8_000_000) as ws:
        t0, n, size = time.time(), 0, 0
        await ws.send(json.dumps({"type": "input", "kind": "scroll", "x": 640, "y": 400, "dy": 300}))
        while time.time() - t0 < 12:
            try:
                m = await asyncio.wait_for(ws.recv(), 1)
            except asyncio.TimeoutError:
                await ws.send(json.dumps({"type": "input", "kind": "scroll", "x": 640, "y": 400, "dy": -300}))
                continue
            if isinstance(m, bytes):
                n += 1
                size += len(m)
            else:
                print("text", m)
        print("frames", n, "avg bytes", size // max(n, 1), "fps", round(n / 12, 1))

asyncio.run(main())
