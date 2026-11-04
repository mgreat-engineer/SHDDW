# Shadow iteration-3: laptop helper (pairing, websocket, target switching, remote browser/files, offline/resume, unlink, cloud regression)
# Run serially: pytest /app/backend/tests/test_laptop_helper.py -n 0 -v -s
import asyncio
import base64
import json
import os
import subprocess
import sys
import time
import urllib.parse

import pytest
import requests
import websockets
from dotenv import dotenv_values

BASE_URL = dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"].rstrip("/")
WS_URL = BASE_URL.replace("https://", "wss://") + "/api/helper/ws"
A_EMAIL = "shadow.a+clerk_test@example.com"
B_EMAIL = "shadow.b+clerk_test@example.com"
PY = "/root/.venv/bin/python"


def client(email):
    s = requests.Session()
    s.headers["Authorization"] = "Bearer " + subprocess.check_output(["python", "/app/tests/clerk_token.py", email], text=True).strip()
    return s


@pytest.fixture(scope="module")
def A():
    return client(A_EMAIL)


@pytest.fixture(scope="module")
def B():
    return client(B_EMAIL)


def stop_active(s):
    r = s.get(f"{BASE_URL}/api/runs/active").json()
    if r.get("run"):
        s.post(f"{BASE_URL}/api/runs/{r['run']['id']}/stop")
        time.sleep(2)


def wait_run(s, rid, until, timeout=240):
    end = time.time() + timeout
    run = None
    while time.time() < end:
        run = s.get(f"{BASE_URL}/api/runs/{rid}").json()
        if run["status"] in until:
            return run
        time.sleep(3)
    return run


def wait_online(s, want=True, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        if s.get(f"{BASE_URL}/api/target").json()["helper_online"] == want:
            return True
        time.sleep(1.5)
    return False


def helper_pids():
    out = subprocess.run(["pgrep", "-f", "helper_sim.py"], capture_output=True, text=True).stdout.split()
    return [int(p) for p in out]


def start_helper():
    env = {**os.environ, "SHADOW_CHROME_PATH": "/usr/bin/google-chrome"}
    subprocess.Popen(f"nohup {PY} /app/tests/helper_sim.py >> /tmp/helper.log 2>&1 &", shell=True, cwd="/app", env=env)


def kill_helper():
    for p in helper_pids():
        os.kill(p, 9)
    subprocess.run(["pkill", "-9", "-f", "helperhome"], capture_output=True)


async def ws_try(token, hold=0.0, on_open=None):
    """Connect; return ('open', close_code) or ('rejected', detail)."""
    try:
        async with websockets.connect(WS_URL, additional_headers={"Authorization": "Bearer " + token}, open_timeout=20) as ws:
            await ws.send(json.dumps({"event": "hello", "info": {"version": "TEST", "folders": ["/x/TEST_f"]}}))
            if on_open:
                await on_open(ws)
            try:
                await asyncio.wait_for(ws.wait_closed(), hold)
            except asyncio.TimeoutError:
                pass
            return "open", ws.close_code
    except Exception as e:
        return "rejected", str(e)[:120]


# ---------- Pairing + websocket + unlink (user B, isolated from A's helper) ----------
class TestPairingAndUnlink:
    def test_pair_code_flow(self, B):
        r = B.post(f"{BASE_URL}/api/devices/pair-code")
        assert r.status_code == 200
        code = r.json()["code"]
        assert len(code) == 8 and code.isalnum() and code.isupper()
        # no auth needed
        p = requests.post(f"{BASE_URL}/api/helper/pair", json={"code": code.lower(), "name": "TEST_B_laptop"})
        assert p.status_code == 200, p.text
        d = p.json()
        assert d["name"] == "TEST_B_laptop" and len(d["token"]) > 20 and d["device_id"]
        # code works once
        again = requests.post(f"{BASE_URL}/api/helper/pair", json={"code": code, "name": "x"})
        assert again.status_code == 400 and "wrong or expired" in again.json()["detail"]
        bad = requests.post(f"{BASE_URL}/api/helper/pair", json={"code": "ZZZZZZZZ"})
        assert bad.status_code == 400
        pytest.B_dev = d

    def test_expired_code(self):
        from pymongo import MongoClient
        env = dotenv_values("/app/backend/.env")
        db = MongoClient(env["MONGO_URL"])[env["DB_NAME"]]
        db.pair_codes.insert_one({"code": "TESTEXP9", "user_id": "TEST_nobody", "expires_at": "2020-01-01T00:00:00+00:00"})
        try:
            r = requests.post(f"{BASE_URL}/api/helper/pair", json={"code": "TESTEXP9"})
            assert r.status_code == 400
        finally:
            db.pair_codes.delete_one({"code": "TESTEXP9"})

    def test_ws_bad_token_rejected(self):
        kind, _ = asyncio.run(ws_try("TEST_bad_token", 1))
        assert kind == "rejected"

    def test_target_laptop_offline_409(self, B):
        assert B.get(f"{BASE_URL}/api/target").json()["helper_online"] is False
        r = B.put(f"{BASE_URL}/api/target", json={"target": "laptop"})
        assert r.status_code == 409
        assert B.put(f"{BASE_URL}/api/target", json={"target": "moon"}).status_code == 400

    def test_ws_valid_connect_online_then_unlink(self, B):
        dev = pytest.B_dev
        result = {}

        async def on_open(ws):
            await asyncio.sleep(2)
            t = B.get(f"{BASE_URL}/api/target").json()
            result["target"] = t
            result["devices"] = B.get(f"{BASE_URL}/api/devices").json()
            result["put"] = B.put(f"{BASE_URL}/api/target", json={"target": "laptop"}).status_code
            result["del"] = B.delete(f"{BASE_URL}/api/devices/{dev['device_id']}").status_code

        kind, code = asyncio.run(ws_try(dev["token"], 10, on_open))
        assert kind == "open"
        t = result["target"]
        assert t["helper_online"] is True and t["helper"]["name"] == "TEST_B_laptop"
        assert t["helper"]["info"]["version"] == "TEST"
        mine = [d for d in result["devices"] if d["id"] == dev["device_id"]]
        assert mine and mine[0]["online"] is True
        assert result["put"] == 200
        assert result["del"] == 200
        assert code == 4401, f"close code {code}"
        after = B.get(f"{BASE_URL}/api/target").json()
        assert after["target"] == "cloud" and after["helper_online"] is False
        assert dev["device_id"] not in [d["id"] for d in B.get(f"{BASE_URL}/api/devices").json()]
        kind2, _ = asyncio.run(ws_try(dev["token"], 1))
        assert kind2 == "rejected"
        assert B.delete(f"{BASE_URL}/api/devices/TEST_nope").status_code == 404


# ---------- Remote browser/files through A's helper simulator ----------
class TestLaptopTarget:
    def test_switch_and_state(self, A):
        stop_active(A)
        assert wait_online(A)
        r = A.put(f"{BASE_URL}/api/target", json={"target": "laptop"})
        assert r.status_code == 200 and r.json()["target"] == "laptop"
        st = A.get(f"{BASE_URL}/api/browser/state")
        assert st.status_code == 200, st.text
        assert st.json()["target"] == "laptop" and "tabs" in st.json()

    def test_frame_navigate_tabs_input(self, A):
        url = "data:text/html," + urllib.parse.quote("<title>TEST_LAPTOP</title><input id=q style='width:500px'>")
        r = A.post(f"{BASE_URL}/api/browser/navigate", json={"url": url})
        assert r.status_code == 200, r.text
        time.sleep(1)
        st = A.get(f"{BASE_URL}/api/browser/state").json()
        assert any(t["title"] == "TEST_LAPTOP" for t in st["tabs"]), st["tabs"]
        f = A.get(f"{BASE_URL}/api/browser/frame")
        assert f.status_code == 200 and f.headers["content-type"] == "image/jpeg" and f.content[:2] == b"\xff\xd8"
        assert A.post(f"{BASE_URL}/api/browser/input", json={"kind": "click", "x": 100, "y": 15}).status_code == 200
        assert A.post(f"{BASE_URL}/api/browser/input", json={"kind": "type", "text": "hi"}).status_code == 200
        n0 = len(st["tabs"])
        t = A.post(f"{BASE_URL}/api/browser/tabs", json={"action": "new", "url": "about:blank"})
        assert t.status_code == 200, t.text
        st2 = A.get(f"{BASE_URL}/api/browser/state").json()
        assert len(st2["tabs"]) == n0 + 1
        active = [x["index"] for x in st2["tabs"] if x["active"]][0]
        c = A.post(f"{BASE_URL}/api/browser/tabs", json={"action": "close", "index": active})
        assert c.status_code == 200
        assert A.post(f"{BASE_URL}/api/browser/nav", json={"action": "reload"}).status_code == 200

    def test_record(self, A):
        assert A.post(f"{BASE_URL}/api/record/start").status_code == 200
        assert A.get(f"{BASE_URL}/api/browser/state").json()["recording"] is True
        assert A.post(f"{BASE_URL}/api/record/note", json={"text": "TEST_note"}).status_code == 200
        ev = A.post(f"{BASE_URL}/api/record/stop").json()["events"]
        assert any("TEST_note" in json.dumps(e) for e in ev), ev

    def test_target_files(self, A):
        r = A.get(f"{BASE_URL}/api/target/files")
        assert r.status_code == 200
        names = [f["name"] for f in r.json()]
        assert "Docs/items.csv" in names
        assert all(f["source"] == "laptop" for f in r.json())

    def test_local_folders_traversal_unit(self):
        sys.path.insert(0, "/app/desktop/shadow_helper")
        sys.path.insert(0, "/app/backend")
        import core

        class C(dict):
            def __getitem__(self, k):
                return self.get(k)
        lf = core.LocalFolders(C(folders=["/tmp/laptop/Docs"], downloads_folder="/tmp/laptop/Docs"))
        assert "outside" in asyncio.run(lf.read("Docs/../../etc/passwd")) or "not inside" in asyncio.run(lf.read("Docs/../../etc/passwd"))
        assert "root:" not in asyncio.run(lf.read("Docs/../../etc/passwd"))
        assert "not inside" in asyncio.run(lf.read("/etc/passwd"))
        with pytest.raises(ValueError):
            asyncio.run(lf.write("Docs/../../tmp/TEST_evil.txt", "x"))


# ---------- Agent on laptop + offline/resume (uses GPT) ----------
class TestLaptopAgent:
    def test_agent_read_write_and_traversal(self, A):
        stop_active(A)
        A.put(f"{BASE_URL}/api/target", json={"target": "laptop"})
        with suppress_missing():
            os.remove("/tmp/laptop/Docs/summary.txt")
        r = A.post(f"{BASE_URL}/api/runs", json={"command": "TEST_ Read Docs/items.csv and write Docs/summary.txt containing only its first line. Then try to read the file Docs/../../etc/passwd and tell me in the finish summary what happened. Do not use the browser."})
        assert r.status_code == 200, r.text
        rid = r.json()["id"]
        assert r.json()["target"] == "laptop"
        # switching while active run -> 409
        assert A.put(f"{BASE_URL}/api/target", json={"target": "cloud"}).status_code == 409
        run = wait_run(A, rid, ("completed", "failed", "paused", "waiting_input", "awaiting_approval"))
        print("RUN1", run["status"], run["summary"])
        for s in reversed(run["steps"]):
            print("  ", s["action"], json.dumps(s["args"])[:120], "->", s["result"][:160])
        assert run["status"] == "completed"
        # seed file may contain a literal "\n"; accept the first logical line
        first = open("/tmp/laptop/Docs/items.csv").read().replace("\\n", "\n").splitlines()[0]
        assert open("/tmp/laptop/Docs/summary.txt").read().strip() == first.strip()
        reads = [s for s in run["steps"] if s["action"] == "read_file" and "passwd" in json.dumps(s["args"])]
        assert reads and all("root:" not in s["result"] for s in reads)

    def test_offline_pause_and_resume(self, A):
        stop_active(A)
        A.put(f"{BASE_URL}/api/target", json={"target": "laptop"})
        r = A.post(f"{BASE_URL}/api/runs", json={"command": "TEST_ Open https://example.com, then https://www.iana.org/help/example-domains, then https://en.wikipedia.org/wiki/Example.com and read each page carefully, writing notes with save_data after each one. Then finish."})
        assert r.status_code == 200, r.text
        rid = r.json()["id"]
        time.sleep(12)
        kill_helper()
        assert wait_online(A, False, 30)
        run = wait_run(A, rid, ("paused", "failed", "completed"), 90)
        print("RUN2 after kill", run["status"], run["summary"])
        assert run["status"] == "paused"
        assert "laptop helper went offline" in run["summary"].lower()
        st = A.get(f"{BASE_URL}/api/browser/state")
        assert st.status_code == 409 and "offline" in st.json()["detail"].lower()
        assert A.get(f"{BASE_URL}/api/target/files").status_code == 409
        assert A.post(f"{BASE_URL}/api/browser/navigate", json={"url": "about:blank"}).status_code == 409
        assert A.post(f"{BASE_URL}/api/runs/{rid}/resume").status_code == 409
        start_helper()
        assert wait_online(A, True, 90)
        res = A.post(f"{BASE_URL}/api/runs/{rid}/resume")
        assert res.status_code == 200, res.text
        time.sleep(15)
        run = A.get(f"{BASE_URL}/api/runs/{rid}").json()
        print("RUN2 after resume", run["status"], run["step_count"], run["summary"])
        assert run["status"] in ("running", "completed")
        A.post(f"{BASE_URL}/api/runs/{rid}/stop")
        time.sleep(2)


# ---------- Cloud regression ----------
class TestCloudRegression:
    def test_cloud_browser_files_record_agent(self, A):
        stop_active(A)
        r = A.put(f"{BASE_URL}/api/target", json={"target": "cloud"})
        assert r.status_code == 200 and r.json()["target"] == "cloud"
        st = A.get(f"{BASE_URL}/api/browser/state").json()
        assert st["target"] == "cloud"
        url = "data:text/html," + urllib.parse.quote("<title>TEST_CLOUD</title><p>hello</p>")
        assert A.post(f"{BASE_URL}/api/browser/navigate", json={"url": url}).status_code == 200
        time.sleep(1)
        assert any(t["title"] == "TEST_CLOUD" for t in A.get(f"{BASE_URL}/api/browser/state").json()["tabs"])
        assert A.get(f"{BASE_URL}/api/browser/frame").status_code == 200
        assert A.post(f"{BASE_URL}/api/browser/input", json={"kind": "scroll", "x": 100, "y": 100, "dy": 100}).status_code == 200
        assert A.post(f"{BASE_URL}/api/record/start").status_code == 200
        A.post(f"{BASE_URL}/api/record/note", json={"text": "TEST_cloudnote"})
        assert any("TEST_cloudnote" in json.dumps(e) for e in A.post(f"{BASE_URL}/api/record/stop").json()["events"])
        up = A.post(f"{BASE_URL}/api/files", files={"file": ("TEST_cloud.csv", b"a,b\n1,2\n")})
        assert up.status_code == 200
        fid = up.json()["id"]
        tf = [f["name"] for f in A.get(f"{BASE_URL}/api/target/files").json()]
        assert "TEST_cloud.csv" in tf
        r = A.post(f"{BASE_URL}/api/runs", json={"command": "TEST_ Read the file TEST_cloud.csv and write TEST_cloud_out.txt containing just its header line. Do not use the browser."})
        assert r.status_code == 200 and r.json()["target"] == "cloud"
        run = wait_run(A, r.json()["id"], ("completed", "failed", "paused", "waiting_input", "awaiting_approval"))
        print("RUN3", run["status"], run["summary"])
        files = A.get(f"{BASE_URL}/api/files").json()
        out = [f for f in files if f["name"] == "TEST_cloud_out.txt"]
        assert run["status"] == "completed" and out
        txt = A.get(f"{BASE_URL}/api/files/{out[0]['id']}/download").text
        assert txt.strip() == "a,b"
        A.delete(f"{BASE_URL}/api/files/{fid}")
        A.delete(f"{BASE_URL}/api/files/{out[0]['id']}")


class suppress_missing:
    def __enter__(self):
        return self

    def __exit__(self, et, ev, tb):
        return et is FileNotFoundError
