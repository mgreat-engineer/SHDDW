# Shadow iteration-6 retest: unique group ids, stale run isolation, resume recreating closed group, 404/400 on close
# Run serially: cd /app/backend && pytest tests/test_iter6_fixes.py -n 0 -v -s
import re
import subprocess
import time
import uuid

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient

BASE_URL = dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
A_EMAIL = "shadow.a+clerk_test@example.com"
ACTIVE = ("running", "paused", "awaiting_approval", "waiting_input")
_BE = dotenv_values("/app/backend/.env")
DB = MongoClient(_BE["MONGO_URL"])[_BE["DB_NAME"]]
CMD = "open example.com and tell me the page title"


@pytest.fixture(scope="module")
def A():
    s = requests.Session()
    s.headers["Authorization"] = "Bearer " + subprocess.check_output(["python", "/app/tests/clerk_token.py", A_EMAIL], text=True).strip()
    return s


@pytest.fixture(scope="module")
def track(A):
    t = {"groups": [], "runs": [], "db_runs": []}
    yield t
    for r in t["runs"]:
        A.post(f"{API}/runs/{r}/stop")
    for r in t["db_runs"]:
        DB.runs.delete_one({"id": r})
    time.sleep(2)
    for g in t["groups"]:
        A.delete(f"{API}/browser/groups/{g}")


def new_group(A, track, name=""):
    r = A.post(f"{API}/browser/groups", json={"name": name, "url": "about:blank"}, timeout=60)
    assert r.status_code == 200, r.text
    track["groups"].append(r.json()["id"])
    return r.json()


def groups(A):
    return A.get(f"{API}/browser/groups", timeout=30).json()["groups"]


def wait_not_running(A, rid, timeout=150):
    end = time.time() + timeout
    while time.time() < end:
        run = A.get(f"{API}/runs/{rid}").json()
        if run["status"] != "running":
            return run
        time.sleep(3)
    return run


# FIX 1: unique random ids, no stale attach
class TestUniqueIds:
    def test_ids_are_random_hex_and_unique(self, A, track):
        ids = []
        for i in range(3):
            g = new_group(A, track, f"TEST_u{i}")
            assert re.fullmatch(r"[0-9a-f]{8}", g["id"]), g["id"]
            ids.append(g["id"])
            assert A.delete(f"{API}/browser/groups/{g['id']}").status_code == 200
            track["groups"].remove(g["id"])
        assert len(set(ids)) == 3

    def test_stale_paused_run_not_attached(self, A, track):
        uid = DB.runs.find_one({"goal": {"$regex": "example.com"}}, sort=[("created_at", -1)])["user_id"]
        stale = []
        for gid in ("2", "3", "4", uuid.uuid4().hex[:8]):
            rid = "TEST_" + str(uuid.uuid4())
            DB.runs.insert_one({"id": rid, "user_id": uid, "goal": "TEST_stale paused", "status": "paused", "group_id": gid,
                                "created_at": "2026-01-01T00:00:00+00:00", "updated_at": "2026-01-01T00:00:00+00:00",
                                "target": "cloud", "plan": [], "messages": [], "step_count": 0, "mode": "real"})
            track["db_runs"].append(rid)
            stale.append(rid)
        g = new_group(A, track, "TEST_fresh")
        info = next(x for x in groups(A) if x["id"] == g["id"])
        assert info["run"] is None
        assert A.get(f"{API}/runs/active", params={"group": g["id"]}).json()["run"] is None
        r = A.post(f"{API}/runs", params={"group": g["id"]}, json={"command": CMD}, timeout=60)
        assert r.status_code == 200, r.text
        assert r.json()["group_id"] == g["id"]
        A.post(f"{API}/runs/{r.json()['id']}/stop")
        track["runs"].append(r.json()["id"])
        time.sleep(2)
        assert A.delete(f"{API}/browser/groups/{g['id']}").status_code == 200
        track["groups"].remove(g["id"])
        for rid in stale:
            DB.runs.delete_one({"id": rid})


# FIX 3: close unknown 404, main 400
class TestClose:
    def test_unknown_404(self, A):
        r = A.delete(f"{API}/browser/groups/zz{uuid.uuid4().hex[:6]}")
        assert r.status_code == 404, r.text

    def test_main_400(self, A):
        r = A.delete(f"{API}/browser/groups/1")
        assert r.status_code == 400
        assert any(g["id"] == "1" for g in groups(A))


# FIX 2: resume recreates closed group; 409 if other task active
class TestResume:
    def test_resume_stopped_recreates_group(self, A, track):
        g = new_group(A, track, "TEST_resume")
        r = A.post(f"{API}/runs", params={"group": g["id"]}, json={"command": CMD}, timeout=60)
        assert r.status_code == 200, r.text
        rid = r.json()["id"]
        track["runs"].append(rid)
        assert A.post(f"{API}/runs/{rid}/stop").status_code == 200
        time.sleep(3)
        assert A.delete(f"{API}/browser/groups/{g['id']}").status_code == 200
        assert all(x["id"] != g["id"] for x in groups(A))
        r = A.post(f"{API}/runs/{rid}/resume", timeout=60)
        assert r.status_code == 200, r.text
        lst = groups(A)
        rec = next((x for x in lst if x["id"] == g["id"]), None)
        assert rec is not None, "group not recreated"
        assert rec["name"].startswith("Resumed: "), rec["name"]
        run = A.get(f"{API}/runs/{rid}").json()
        assert run["group_id"] == g["id"]
        assert run["status"] in ACTIVE + ("completed", "failed")
        print("resumed run status", run["status"], "group chip run:", rec["run"])
        final = wait_not_running(A, rid)
        print("final", final["status"], final.get("summary", "")[:120])
        if final["status"] in ACTIVE:
            A.post(f"{API}/runs/{rid}/stop")

    def test_resume_failed_and_409(self, A, track):
        g = new_group(A, track, "TEST_r409")
        r1 = A.post(f"{API}/runs", params={"group": g["id"]}, json={"command": CMD}, timeout=60).json()
        track["runs"].append(r1["id"])
        A.post(f"{API}/runs/{r1['id']}/stop")
        time.sleep(2)
        DB.runs.update_one({"id": r1["id"]}, {"$set": {"status": "failed"}})
        r2 = A.post(f"{API}/runs", params={"group": g["id"]}, json={"command": CMD}, timeout=60)
        assert r2.status_code == 200, r2.text
        track["runs"].append(r2.json()["id"])
        r = A.post(f"{API}/runs/{r1['id']}/resume", timeout=60)
        assert r.status_code == 409, r.text
        A.post(f"{API}/runs/{r2.json()['id']}/stop")
        time.sleep(2)
        # now resume the failed one in its still-open group
        r = A.post(f"{API}/runs/{r1['id']}/resume", timeout=60)
        assert r.status_code == 200, r.text
        assert A.get(f"{API}/runs/{r1['id']}").json()["group_id"] == g["id"]
        A.post(f"{API}/runs/{r1['id']}/stop")

    def test_resume_completed_400(self, A):
        done = A.get(f"{API}/runs").json()
        c = next((x for x in done if x["status"] == "completed"), None)
        if not c:
            pytest.skip("no completed run")
        assert A.post(f"{API}/runs/{c['id']}/resume").status_code == 400
