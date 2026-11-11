# Probe: WS 'move' during a running task must not pause it; 'click' does pause (take over). python iter9_move_probe.py <group>
import asyncio, json, subprocess, sys, time
import requests, websockets

BASE = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].rstrip("/")
API = BASE + "/api"
tok = subprocess.check_output([sys.executable, "/app/tests/clerk_token.py", "shadow.a+clerk_test@example.com"]).decode().strip()
H = {"Authorization": "Bearer " + tok}
g = sys.argv[1]
r = requests.post(API + f"/runs?group={g}", json={"command": "TEST_ open example.com, then wait 20 seconds, then tell me the page title"}, headers=H)
print("start", r.status_code, r.json().get("status"))
rid = r.json()["id"]


async def main():
    async with websockets.connect(API.replace("https://", "wss://") + f"/browser/stream?token={tok}&group={g}", max_size=8_000_000) as ws:
        await asyncio.sleep(4)
        for i in range(10):
            await ws.send(json.dumps({"type": "input", "kind": "move", "x": 100 + i * 10, "y": 200}))
            await asyncio.sleep(0.1)
        await asyncio.sleep(1.5)
        print("after moves:", requests.get(API + f"/runs/{rid}", headers=H).json()["status"])
        await ws.send(json.dumps({"type": "input", "kind": "click", "x": 5, "y": 5}))
        await asyncio.sleep(2)
        print("after click:", requests.get(API + f"/runs/{rid}", headers=H).json()["status"])

asyncio.run(main())
st = requests.get(API + f"/runs/{rid}", headers=H).json()["status"]
if st in ("running", "paused"):
    print("stop", requests.post(API + f"/runs/{rid}/stop", headers=H).status_code)
