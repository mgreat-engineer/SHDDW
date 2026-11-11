# Probe: does resize actually change the page viewport (JPEG dims + innerWidth)? python iter9_resize_probe.py [group]
import asyncio, io, json, subprocess, sys, time
import requests, websockets
from PIL import Image

BASE = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].rstrip("/")
API = BASE + "/api"
tok = subprocess.check_output([sys.executable, "/app/tests/clerk_token.py", "shadow.a+clerk_test@example.com"]).decode().strip()
H = {"Authorization": "Bearer " + tok}
PAGE = "data:text/html,<style>@keyframes m{from{margin-left:0}to{margin-left:300px}}div{width:50px;height:50px;background:green;animation:m 2s linear infinite}</style><div></div><script>setInterval(()=>document.title=innerWidth+'x'+innerHeight,200)</script>"


def dims(b):
    return Image.open(io.BytesIO(b)).size


async def main(g, nav):
    if nav:
        requests.post(API + f"/browser/navigate?group={g}", json={"url": PAGE}, headers=H)
    async with websockets.connect(API.replace("https://", "wss://") + f"/browser/stream?token={tok}&group={g}", max_size=8_000_000) as ws:
        for w, h in [(1058, 821), (900, 600), (1280, 800)]:
            await ws.send(json.dumps({"type": "resize", "width": w, "height": h}))
            last, t0 = None, time.time()
            while time.time() - t0 < 2.5:
                try:
                    m = await asyncio.wait_for(ws.recv(), 0.5)
                    if isinstance(m, bytes): last = m
                except asyncio.TimeoutError:
                    pass
            st = requests.get(API + f"/browser/state?group={g}", headers=H).json()
            title = [t for t in st["tabs"] if t["active"]][0]["title"]
            print(f"resize {w}x{h}: state vp={st['viewport']} frame={dims(last) if last else None} title={title[:30]}",
                  "GET /frame:", dims(requests.get(API + f"/browser/frame?group={g}", headers=H).content))


if len(sys.argv) > 1:
    asyncio.run(main(sys.argv[1], False))
else:
    g = requests.post(API + "/browser/groups", json={"name": "TEST_resize"}, headers=H).json()["id"]
    try:
        asyncio.run(main(g, True))
    finally:
        print("cleanup", requests.delete(API + f"/browser/groups/{g}", headers=H).status_code)
