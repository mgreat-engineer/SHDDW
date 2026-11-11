# Probe: reconnect stream with an already-applied viewport; are screencast frames the right size? python iter9_reconnect_probe.py
import asyncio, io, json, subprocess, sys, time
import requests, websockets
from PIL import Image

BASE = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].rstrip("/")
API = BASE + "/api"
tok = subprocess.check_output([sys.executable, "/app/tests/clerk_token.py", "shadow.a+clerk_test@example.com"]).decode().strip()
H = {"Authorization": "Bearer " + tok}
PAGE = "data:text/html,<style>@keyframes m{from{margin-left:0}to{margin-left:300px}}div{width:50px;height:50px;background:green;animation:m 2s linear infinite}</style><div></div>"
URL = API.replace("https://", "wss://") + "/browser/stream?token={}&group={}"


async def session(g, resize=None, secs=3):
    sizes = {}
    async with websockets.connect(URL.format(tok, g), max_size=8_000_000) as ws:
        if resize:
            await ws.send(json.dumps({"type": "resize", "width": resize[0], "height": resize[1]}))
        t0 = time.time()
        while time.time() - t0 < secs:
            try:
                m = await asyncio.wait_for(ws.recv(), 0.5)
                if isinstance(m, bytes):
                    s = Image.open(io.BytesIO(m)).size
                    sizes[s] = sizes.get(s, 0) + 1
            except asyncio.TimeoutError:
                pass
    return sizes


g = requests.post(API + "/browser/groups", json={"name": "TEST_reconnect"}, headers=H).json()["id"]
try:
    requests.post(API + f"/browser/navigate?group={g}", json={"url": sys.argv[1] if len(sys.argv) > 1 else PAGE}, headers=H)
    print("connect+resize 1000x700:", asyncio.run(session(g, (1000, 700))))
    print("reconnect same size    :", asyncio.run(session(g, (1000, 700))))
    print("reconnect no resize    :", asyncio.run(session(g)))
    requests.post(API + f"/browser/tabs?group={g}", json={"action": "new", "url": PAGE}, headers=H)
    print("new tab after resize   :", asyncio.run(session(g)))
finally:
    print("cleanup", requests.delete(API + f"/browser/groups/{g}", headers=H).status_code)
