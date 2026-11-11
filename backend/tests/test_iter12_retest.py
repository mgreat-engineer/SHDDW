# Shadow iteration-12 retest: input latency, WS selection ordering after drag, Accept-Language header,
# failed-login no save offer, offer expiry. Uses a dedicated TEST_ workspace (deleted at end).
# Run: cd /app/backend && pytest tests/test_iter12_retest.py -n 0 -v -s
import asyncio
import json
import subprocess
import time

import pytest
import requests
import websockets
from dotenv import dotenv_values

BASE_URL = dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
WS = BASE_URL.replace("https://", "wss://") + "/api/browser/stream"
A_EMAIL = "shadow.a+clerk_test@example.com"
ORIGIN = "https://the-internet.herokuapp.com"


def token(email=A_EMAIL):
    return subprocess.check_output(["python", "/app/tests/clerk_token.py", email], text=True).strip()


@pytest.fixture(scope="module")
def A():
    s = requests.Session()
    s.headers["Authorization"] = "Bearer " + token()
    return s


@pytest.fixture(scope="module")
def ws(A):
    r = A.post(f"{API}/browser/groups", json={"name": "TEST_iter12", "url": "https://example.com"}, timeout=60)
    assert r.status_code == 200, r.text
    g = r.json().get("id") or r.json().get("group", {}).get("id")
    yield g
    A.delete(f"{API}/browser/groups/{g}", timeout=60)


def state(A, g):
    r = A.get(f"{API}/browser/state?group={g}", timeout=60)
    assert r.status_code == 200, r.text
    return r.json()


def active_url(st):
    return next(t["url"] for t in st["tabs"] if t["active"])


# ---------- input latency ----------
def test_input_latency(A, ws):
    A.post(f"{API}/browser/navigate?group={ws}", json={"url": "https://example.com"}, timeout=60)
    times = {}
    for kind, extra in (("move", {"x": 100, "y": 100}), ("down", {"x": 100, "y": 100}), ("up", {"x": 100, "y": 100}),
                        ("type", {"text": "a"})):
        ts = []
        for _ in range(4):
            t0 = time.time()
            r = A.post(f"{API}/browser/input?group={ws}", json={"kind": kind, **extra})
            ts.append(time.time() - t0)
            assert r.status_code == 200, r.text
        times[kind] = sorted(ts)[len(ts) // 2]
    t0 = time.time(); A.get(f"{API}/bookmarks"); base = time.time() - t0
    print("median input times:", times, "plain GET:", round(base, 3))
    for k, v in times.items():
        assert v < base + 0.15, f"{k} too slow: {v:.3f}s (GET {base:.3f}s)"


# ---------- drag then immediate selection over the same WS ----------
def test_drag_then_ws_selection_full(A, ws):
    A.post(f"{API}/browser/navigate?group={ws}", json={"url": "https://example.com"}, timeout=60)
    time.sleep(1.5)
    t = token()

    async def go():
        async with websockets.connect(f"{WS}?token={t}&group={ws}", max_size=8_000_000) as w:
            await w.send(json.dumps({"type": "resize", "width": 1280, "height": 800}))
            await asyncio.sleep(1.5)
            # drag from heading start across both paragraphs
            await w.send(json.dumps({"type": "input", "kind": "move", "x": 330, "y": 140}))
            await w.send(json.dumps({"type": "input", "kind": "down", "x": 330, "y": 140}))
            for i in range(1, 25):
                await w.send(json.dumps({"type": "input", "kind": "move", "x": 330 + i * 25, "y": 140 + i * 12}))
            await w.send(json.dumps({"type": "input", "kind": "up", "x": 930, "y": 430}))
            await w.send(json.dumps({"type": "selection", "id": "s1"}))
            t0 = time.time()
            while time.time() - t0 < 15:
                m = await w.recv()
                if isinstance(m, str):
                    d = json.loads(m)
                    if d.get("type") == "selection":
                        return d.get("text"), time.time() - t0
            return None, None
    text, dt = asyncio.run(go())
    time.sleep(2)
    later = A.get(f"{API}/browser/selection?group={ws}").json()["text"]
    print(f"ws selection ({dt}s): {text!r}\nlater: {later!r}")
    assert text and len(text) > 20
    assert text == later


# ---------- headers ----------
def test_accept_language_and_ua(A, ws):
    A.post(f"{API}/browser/navigate?group={ws}", json={"url": "https://httpbin.org/headers"}, timeout=60)
    time.sleep(1.5)
    A.post(f"{API}/browser/input?group={ws}", json={"kind": "key", "key": "Control+a"})
    time.sleep(0.5)
    txt = A.get(f"{API}/browser/selection?group={ws}").json()["text"]
    print(txt[:1500])
    al = [l for l in txt.splitlines() if '"Accept-Language"' in l]
    assert al and '"en-US,en;q=0.9"' in al[0], al
    ua = [l for l in txt.splitlines() if '"User-Agent"' in l]
    assert ua and "Chrome/" in ua[0] and "HeadlessChrome" not in ua[0]


# ---------- failed login: no offer; then navigate away; then expiry ----------
def test_failed_login_no_offer(A, ws):
    A.post(f"{API}/browser/navigate?group={ws}", json={"url": ORIGIN + "/login"}, timeout=60)
    time.sleep(1.5)
    st = state(A, ws)
    assert st["saved_logins"], "tomsmith must be saved for this test"
    r = A.post(f"{API}/passwords/{st['saved_logins'][0]['id']}/fill?group={ws}")
    assert r.status_code == 200, r.text
    A.post(f"{API}/browser/input?group={ws}", json={"kind": "type", "text": "WRONG"})
    A.post(f"{API}/browser/input?group={ws}", json={"kind": "key", "key": "Enter"})
    time.sleep(3)
    st = state(A, ws)
    print("after failed login:", active_url(st), st["save_password"], st["has_password_field"])
    assert "/login" in active_url(st) and st["has_password_field"]
    assert st["save_password"] is None
    # navigate away within 90s - does the stale wrong-password offer reappear?
    A.post(f"{API}/browser/navigate?group={ws}", json={"url": "https://example.com"}, timeout=60)
    time.sleep(1.5)
    st2 = state(A, ws)
    print("after navigating away:", active_url(st2), st2["save_password"])
    pytest.stale_offer = st2["save_password"]
    A.post(f"{API}/passwords/offer?group={ws}", json={"action": "dismiss"})
