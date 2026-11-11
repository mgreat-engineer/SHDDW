# Probe: group 1 (persistent context) screencast frame sizes after resize, on static wikipedia + an animated temp tab. python iter9_main_probe.py
import asyncio, io, json, subprocess, sys, time
import requests, websockets
from PIL import Image

BASE = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].rstrip("/")
API = BASE + "/api"
tok = subprocess.check_output([sys.executable, "/app/tests/clerk_token.py", "shadow.a+clerk_test@example.com"]).decode().strip()
H = {"Authorization": "Bearer " + tok}
PAGE = "data:text/html,<style>@keyframes m{from{margin-left:0}to{margin-left:300px}}div{width:50px;height:50px;background:green;animation:m 2s linear infinite}</style><div></div>"
URL = API.replace("https://", "wss://") + "/browser/stream?token={}&group=1"


async def session(resize=None, secs=3, before=None):
    sizes = []
    async with websockets.connect(URL.format(tok), max_size=8_000_000) as ws:
        if resize:
            await ws.send(json.dumps({"type": "resize", "width": resize[0], "height": resize[1]}))
        if before:
            await asyncio.sleep(1); before()
        t0 = time.time()
        while time.time() - t0 < secs:
            try:
                m = await asyncio.wait_for(ws.recv(), 0.5)
                if isinstance(m, bytes):
                    s = Image.open(io.BytesIO(m)).size
                    if not sizes or sizes[-1][0] != s: sizes.append([s, 1])
                    else: sizes[-1][1] += 1
            except asyncio.TimeoutError:
                pass
    return sizes


print("static wiki resize 1058x821:", asyncio.run(session((1058, 821))))
print("static wiki reconnect      :", asyncio.run(session()))
st = requests.get(API + "/browser/state?group=1", headers=H).json()
n = len(st["tabs"])
requests.post(API + "/browser/tabs?group=1", json={"action": "new", "url": PAGE}, headers=H)
print("anim tab                   :", asyncio.run(session()))
requests.post(API + "/browser/tabs?group=1", json={"action": "close", "index": n}, headers=H)
requests.post(API + "/browser/tabs?group=1", json={"action": "switch", "index": 0}, headers=H)
print("tabs restored:", [t["url"] for t in requests.get(API + "/browser/state?group=1", headers=H).json()["tabs"]])
