# Probe: stream fps on an animated page in a TEST workspace, and page visibility state (python iter9_fps_probe.py)
import asyncio, subprocess, sys, time
import requests, websockets

BASE = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].rstrip("/")
API = BASE + "/api"
tok = subprocess.check_output([sys.executable, "/app/tests/clerk_token.py", "shadow.a+clerk_test@example.com"]).decode().strip()
H = {"Authorization": "Bearer " + tok}
PAGES = {
    "interval": "data:text/html,<div id=b style='width:200px;height:200px;background:red'></div><script>let i=0;setInterval(()=>{i++;b.style.marginLeft=(i%600)+'px';document.title=document.visibilityState+' '+document.hasFocus()},16)</script>",
    "raf": "data:text/html,<div id=b style='width:200px;height:200px;background:blue'></div><script>let i=0;function f(){i++;b.style.marginLeft=(i%600)+'px';document.title=document.visibilityState+' raf'+i;requestAnimationFrame(f)}f()</script>",
    "css": "data:text/html,<style>@keyframes m{from{margin-left:0}to{margin-left:600px}}div{width:200px;height:200px;background:green;animation:m 2s linear infinite}</style><div></div>",
}


async def measure(gid, secs=6):
    async with websockets.connect(API.replace("https://", "wss://") + f"/browser/stream?token={tok}&group={gid}", max_size=8_000_000) as ws:
        t0, n = time.time(), 0
        while time.time() - t0 < 1.5:
            try: await asyncio.wait_for(ws.recv(), 0.5)
            except asyncio.TimeoutError: pass
        t0 = time.time()
        while time.time() - t0 < secs:
            try:
                m = await asyncio.wait_for(ws.recv(), 0.5)
                n += isinstance(m, bytes)
            except asyncio.TimeoutError:
                pass
        return n / secs


g = requests.post(API + "/browser/groups", json={"name": "TEST_fps"}, headers=H).json()["id"]
try:
    for name, url in PAGES.items():
        requests.post(API + f"/browser/navigate?group={g}", json={"url": url}, headers=H)
        fps = asyncio.run(measure(g))
        title = [t for t in requests.get(API + f"/browser/state?group={g}", headers=H).json()["tabs"] if t["active"]][0]["title"]
        print(f"{name}: fps={fps:.1f} title={title!r}")
finally:
    print("cleanup", requests.delete(API + f"/browser/groups/{g}", headers=H).status_code)
