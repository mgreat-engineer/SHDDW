# Helper: force a group's viewport via the stream WS resize. python iter10_setvp.py <group> <w> <h>
import asyncio, json, subprocess, sys
import websockets

BASE = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].rstrip("/")
tok = subprocess.check_output([sys.executable, "/app/tests/clerk_token.py", "shadow.a+clerk_test@example.com"]).decode().strip()
g, w, h = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])


async def main():
    async with websockets.connect(BASE.replace("https://", "wss://") + f"/api/browser/stream?token={tok}&group={g}", max_size=8_000_000) as ws:
        await ws.send(json.dumps({"type": "resize", "width": w, "height": h}))
        await asyncio.sleep(2)

asyncio.run(main())
print("set", g, w, h)
