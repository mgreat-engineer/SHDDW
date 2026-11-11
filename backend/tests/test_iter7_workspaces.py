# Shadow iteration-7: isolated workspaces (labels, cookie isolation, persistence across restart, pause-all/resume-all, prompt label)
# Run serially: cd /app/backend && pytest tests/test_iter7_workspaces.py -n 0 -v -s
import subprocess
import time

import pytest
import requests
from dotenv import dotenv_values

BASE_URL = dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
A_EMAIL = "shadow.a+clerk_test@example.com"
ACTIVE = ("running", "paused", "awaiting_approval", "waiting_input")
SLOW = "open example.com, then wait 20 seconds, then tell me the page title"


def token():
    return subprocess.check_output(["python", "/app/tests/clerk_token.py", A_EMAIL], text=True).strip()


@pytest.fixture(scope="module")
def A():
    s = requests.Session()
    s.headers["Authorization"] = "Bearer " + token()
    return s


@pytest.fixture(scope="module")
def created(A):
    ids, rids = [], []
    yield ids, rids
    for r in rids:
        A.post(f"{API}/runs/{r}/stop", timeout=30)
    for g in ids:
        A.delete(f"{API}/browser/groups/{g}", timeout=60)


def new_ws(A, created, **body):
    r = A.post(f"{API}/browser/groups", json=body, timeout=90)
    assert r.status_code == 200, r.text
    created[0].append(r.json()["id"])
    return r.json()


def groups(A):
    r = A.get(f"{API}/browser/groups", timeout=90)
    assert r.status_code == 200, r.text
    return {g["id"]: g for g in r.json()["groups"]}


def nav(A, gid, url):
    r = A.post(f"{API}/browser/navigate", params={"group": gid}, json={"url": url}, timeout=60)
    assert r.status_code == 200, r.text


def frame(A, gid, path):
    r = A.get(f"{API}/browser/frame", params={"group": gid, "quality": 80}, timeout=30)
    assert r.status_code == 200
    open(path, "wb").write(r.content)


def run_status(A, rid):
    return A.get(f"{API}/runs/{rid}", timeout=30).json()


def wait_status(A, rid, ok=("completed", "failed", "stopped", "waiting_input"), timeout=180):
    end = time.time() + timeout
    while time.time() < end:
        run = run_status(A, rid)
        if run["status"] in ok:
            return run
        time.sleep(3)
    return run


def start_run(A, created, gid, cmd):
    r = A.post(f"{API}/runs", params={"group": gid}, json={"command": cmd}, timeout=60)
    assert r.status_code == 200, r.text
    created[1].append(r.json()["id"])
    return r.json()["id"]


# ---- label CRUD
class TestLabels:
    def test_create_with_label_and_edit(self, A, created):
        g = new_ws(A, created, name="TEST_lab", label="TEST Client Co", url="https://example.com")
        assert g["name"] == "TEST_lab" and g["label"] == "TEST Client Co" and "example.com" in g["url"]
        assert any("example.com" in u for u in g["urls"])
        lst = groups(A)
        assert lst[g["id"]]["label"] == "TEST Client Co"
        r = A.put(f"{API}/browser/groups/{g['id']}", json={"name": "TEST_lab2", "label": "TEST Other"})
        assert r.status_code == 200 and r.json()["name"] == "TEST_lab2" and r.json()["label"] == "TEST Other"
        # name only keeps label
        r = A.put(f"{API}/browser/groups/{g['id']}", json={"name": "TEST_lab3"})
        assert r.status_code == 200 and r.json()["label"] == "TEST Other"
        # clear label
        r = A.put(f"{API}/browser/groups/{g['id']}", json={"name": "TEST_lab3", "label": ""})
        assert r.status_code == 200 and r.json()["label"] == ""
        assert groups(A)[g["id"]]["label"] == ""


# ---- cookie isolation (frames saved to /tmp for visual inspection)
class TestCookieIsolation:
    def test_isolation(self, A, created):
        a = new_ws(A, created, name="TEST_ckA", label="TEST A")["id"]
        b = new_ws(A, created, name="TEST_ckB", label="TEST B")["id"]
        nav(A, a, "https://httpbin.org/cookies/set?ws=a")
        nav(A, b, "https://httpbin.org/cookies/set?ws=b")
        for gid in (a, b, "1"):
            nav(A, gid, "https://httpbin.org/cookies")
        time.sleep(1.5)
        frame(A, a, "/tmp/iso_a.jpg")
        frame(A, b, "/tmp/iso_b.jpg")
        frame(A, "1", "/tmp/iso_main.jpg")
        print("ISO_IDS", a, b)


# ---- pause all / resume all
class TestPauseAll:
    def test_pause_resume_all(self, A, created):
        g1 = new_ws(A, created, name="TEST_pa1")["id"]
        g2 = new_ws(A, created, name="TEST_pa2")["id"]
        r1 = start_run(A, created, g1, SLOW)
        r2 = start_run(A, created, g2, SLOW)
        time.sleep(4)
        p = A.post(f"{API}/runs/pause-all", timeout=60)
        assert p.status_code == 200, p.text
        print("pause-all:", p.json())
        assert p.json()["paused"] >= 2
        assert run_status(A, r1)["status"] == "paused" and run_status(A, r2)["status"] == "paused"
        lst = groups(A)
        assert lst[g1]["run"]["status"] == "paused" and lst[g2]["run"]["status"] == "paused"
        time.sleep(3)
        q = A.post(f"{API}/runs/resume-all", timeout=90)
        assert q.status_code == 200, q.text
        print("resume-all:", q.json())
        assert q.json()["resumed"] >= 2
        s1, s2 = run_status(A, r1), run_status(A, r2)
        assert s1["status"] == "running" and s2["status"] == "running"
        assert s1["group_id"] == g1 and s2["group_id"] == g2
        d1 = wait_status(A, r1)
        d2 = wait_status(A, r2)
        print("pa runs:", d1["status"], d1.get("summary"), "|", d2["status"], d2.get("summary"))
        assert d1["status"] == "completed" and d2["status"] == "completed"
        assert len(groups(A)) >= 2  # workspaces not recreated / duplicated
        assert sum(1 for x in groups(A) if x == g1) == 1

    def test_pause_all_none(self, A):
        # nothing running of ours -> may still be 0
        p = A.post(f"{API}/runs/pause-all", timeout=60)
        assert p.status_code == 200 and isinstance(p.json()["paused"], int)


# ---- workspace label in agent prompt
class TestPromptLabel:
    def test_agent_knows_client(self, A, created):
        g = new_ws(A, created, name="TEST_Mercy", label="Mercy Hospital TESTX")["id"]
        rid = start_run(A, created, g, "Do not browse. Just tell me which client/company this workspace is for, then finish.")
        d = wait_status(A, rid, timeout=120)
        print("prompt run:", d["status"], d.get("summary"))
        assert d["status"] == "completed"
        assert "Mercy" in (d.get("summary") or "")


def test_unauth_401():
    assert requests.post(f"{API}/runs/pause-all", timeout=30).status_code == 401
    assert requests.post(f"{API}/runs/resume-all", timeout=30).status_code == 401
