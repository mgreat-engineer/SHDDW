# Shadow iteration-9: live Chrome screencast WebSocket (/api/browser/stream): auth/group validation, fps,
# tab-switch following, input kinds (click/type/key/scroll/move/dblclick), resize -> viewport (clamped).
# Uses a dedicated TEST_ workspace (created and closed by the tests). Run: cd /app/backend && pytest tests/test_iter9_stream.py -n 0 -v -s
import asyncio
import hashlib
import json
import subprocess
import time

import pytest
import requests
import websockets
from dotenv import dotenv_values

BASE_URL = dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
WS = API.replace("https://", "wss://") + "/browser/stream"
A_EMAIL = "shadow.a+clerk_test@example.com"
ANIM = "data:text/html,<style>@keyframes m{from{margin-left:0}to{margin-left:600px}}div{width:200px;height:200px;background:green;animation:m 2s linear infinite}</style><div></div>"


def token(email=A_EMAIL):
    return subprocess.check_output(["python", "/app/tests/clerk_token.py", email], text=True).strip()


@pytest.fixture(scope="module")
def A():
    s = requests.Session()
    s.headers["Authorization"] = "Bearer " + token()
    return s


@pytest.fixture(scope="module")
def gid(A):
    r = A.post(f"{API}/browser/groups", json={"name": "TEST_stream", "url": "https://example.com"})
    assert r.status_code == 200, r.text
    g = r.json()["id"]
    yield g
    A.delete(f"{API}/browser/groups/{g}")


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


async def collect(ws, secs):
    n, last, t0 = 0, None, time.time()
    while time.time() - t0 < secs:
        try:
            m = await asyncio.wait_for(ws.recv(), 0.5)
        except asyncio.TimeoutError:
            continue
        if isinstance(m, bytes):
            n += 1
            last = m
    return n, last


# --- auth / validation ---
def test_invalid_token_closes_4401():
    async def go():
        try:
            async with websockets.connect(f"{WS}?token=bad&group=1") as ws:
                await ws.recv()
        except websockets.exceptions.ConnectionClosed as e:
            return ("closed", e.rcvd.code if e.rcvd else None)
        except websockets.exceptions.InvalidStatus as e:
            return ("http", e.response.status_code)
        except Exception as e:  # noqa
            return ("other", repr(e))
    res = run(go())
    print("invalid token ->", res)
    assert res == ("closed", 4401), f"expected close 4401, got {res}"


def test_bad_group_closes_4400():
    t = token()

    async def go():
        try:
            async with websockets.connect(f"{WS}?token={t}&group=BAD!!") as ws:
                await ws.recv()
        except websockets.exceptions.ConnectionClosed as e:
            return ("closed", e.rcvd.code if e.rcvd else None)
        except websockets.exceptions.InvalidStatus as e:
            return ("http", e.response.status_code)
        except Exception as e:  # noqa
            return ("other", repr(e))
    res = run(go())
    print("bad group ->", res)
    assert res == ("closed", 4400), f"expected 4400, got {res}"


def test_unknown_group_sends_error(A):
    t = token()

    async def go():
        async with websockets.connect(f"{WS}?token={t}&group=zz999") as ws:
            m = await asyncio.wait_for(ws.recv(), 10)
            return m
    m = run(go())
    print("unknown group ->", m)
    assert isinstance(m, str) and json.loads(m)["type"] == "error"


# --- streaming fps on animated page + resize + inputs ---
def test_stream_fps_and_resize(A, gid):
    r = A.post(f"{API}/browser/navigate?group={gid}", json={"url": ANIM})
    assert r.status_code == 200, r.text
    t = token()

    async def go():
        async with websockets.connect(f"{WS}?token={t}&group={gid}", max_size=8_000_000) as ws:
            await collect(ws, 2)
            n, last = await collect(ws, 6)
            fps = n / 6
            await ws.send(json.dumps({"type": "resize", "width": 1000, "height": 700}))
            await collect(ws, 2)
            vp1 = A.get(f"{API}/browser/state?group={gid}").json()["viewport"]
            await ws.send(json.dumps({"type": "resize", "width": 100, "height": 99999}))
            await collect(ws, 2)
            vp2 = A.get(f"{API}/browser/state?group={gid}").json()["viewport"]
            await ws.send(json.dumps({"type": "resize", "width": 5000, "height": 10}))
            await collect(ws, 2)
            vp3 = A.get(f"{API}/browser/state?group={gid}").json()["viewport"]
            await ws.send(json.dumps({"type": "resize", "width": "abc", "height": None}))
            n2, _ = await collect(ws, 2)
            vp4 = A.get(f"{API}/browser/state?group={gid}").json()["viewport"]
            await ws.send(json.dumps({"type": "resize", "width": 1280, "height": 800}))
            await collect(ws, 1.5)
            return fps, len(last or b""), vp1, vp2, vp3, vp4, n2
    fps, sz, vp1, vp2, vp3, vp4, n2 = run(go())
    print(f"fps={fps:.1f} lastsize={sz} vp1={vp1} vp2={vp2} vp3={vp3} vp4={vp4} frames-after-bad-resize={n2}")
    assert fps >= 15, f"fps too low: {fps}"
    assert vp1 == {"width": 1000, "height": 700}
    assert vp2 == {"width": 640, "height": 1600}
    assert vp3 == {"width": 2560, "height": 400}
    assert vp4 == vp3 and n2 > 0


def test_inputs_drive_page(A, gid):
    A.post(f"{API}/browser/navigate?group={gid}", json={"url": "https://en.wikipedia.org/wiki/Special:Search"})
    t = token()

    async def go():
        async with websockets.connect(f"{WS}?token={t}&group={gid}", max_size=8_000_000) as ws:
            await collect(ws, 2)
            for k in ("move", "click", "dblclick"):
                await ws.send(json.dumps({"type": "input", "kind": k, "x": 300, "y": 300}))
            await ws.send(json.dumps({"type": "input", "kind": "scroll", "x": 640, "y": 400, "dy": 400}))
            await ws.send(json.dumps({"type": "input", "kind": "bogus"}))
            errs = []
            t0 = time.time()
            while time.time() - t0 < 3:
                try:
                    m = await asyncio.wait_for(ws.recv(), 0.5)
                    if isinstance(m, str):
                        errs.append(m)
                except asyncio.TimeoutError:
                    pass
            # navigate to google-free search via typing into wikipedia search box
            A.post(f"{API}/browser/navigate?group={gid}", json={"url": "https://en.wikipedia.org/w/index.php?search="})
            await collect(ws, 2)
            return errs
    errs = run(go())
    print("errors from ws:", errs)
    assert any("Unknown input" in e for e in errs), "bogus input should yield error message"


def test_type_and_key_via_ws(A, gid):
    # page with focused input; type + Enter submit changes the URL hash
    page = "data:text/html,<input id=q style='position:absolute;left:0;top:0;width:400px;height:100px'><script>q.addEventListener('keydown',e=>{if(e.key==='Enter')document.title='v='+q.value})</script>"
    A.post(f"{API}/browser/navigate?group={gid}", json={"url": page})
    t = token()

    async def go():
        async with websockets.connect(f"{WS}?token={t}&group={gid}", max_size=8_000_000) as ws:
            await collect(ws, 1.5)
            await ws.send(json.dumps({"type": "input", "kind": "click", "x": 50, "y": 50}))
            await ws.send(json.dumps({"type": "input", "kind": "type", "text": "hello"}))
            await ws.send(json.dumps({"type": "input", "kind": "key", "key": "Enter"}))
            await collect(ws, 2)
    run(go())
    tabs = A.get(f"{API}/browser/state?group={gid}").json()["tabs"]
    url = [x for x in tabs if x["active"]][0]["title"]
    print("title after typing:", url)
    assert url == "v=hello"


def test_stream_follows_tab_switch(A, gid):
    A.post(f"{API}/browser/navigate?group={gid}", json={"url": "https://example.com"})
    t = token()

    async def go():
        async with websockets.connect(f"{WS}?token={t}&group={gid}", max_size=8_000_000) as ws:
            await collect(ws, 2)
            r = A.post(f"{API}/browser/tabs?group={gid}", json={"action": "new", "url": "https://httpbin.org/html"})
            assert r.status_code == 200, r.text
            _, f_new = await collect(ws, 3)
            st = A.get(f"{API}/browser/state?group={gid}").json()
            A.post(f"{API}/browser/tabs?group={gid}", json={"action": "switch", "index": 0})
            _, f_old = await collect(ws, 3)
            A.post(f"{API}/browser/tabs?group={gid}", json={"action": "switch", "index": len(st["tabs"]) - 1})
            _, f_new2 = await collect(ws, 3)
            A.post(f"{API}/browser/tabs?group={gid}", json={"action": "close", "index": len(st["tabs"]) - 1})
            return f_new, f_old, f_new2
    f_new, f_old, f_new2 = run(go())
    h = lambda b: hashlib.md5(b or b"").hexdigest()  # noqa
    print("frames:", len(f_new or b""), len(f_old or b""), len(f_new2 or b""))
    assert f_new and f_old and f_new2
    assert h(f_new) != h(f_old)
    # sizes should be close for the same page
    assert abs(len(f_new2) - len(f_new)) < 0.15 * len(f_new)
