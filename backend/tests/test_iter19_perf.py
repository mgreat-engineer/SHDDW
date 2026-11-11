# Iteration 19: performance fix - fast /browser/groups on cold start (saved workspaces), background prewarm,
# laptop-offline fallback, per-user browser start lock, workspace CRUD regression
import subprocess, time, threading
import pytest, requests
from dotenv import dotenv_values
from pymongo import MongoClient

BASE_URL = dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"].rstrip("/")
A_EMAIL = "shadow.a+clerk_test@example.com"
B_EMAIL = "shadow.b+clerk_test@example.com"
_env = dotenv_values("/app/backend/.env")
db = MongoClient(_env["MONGO_URL"])[_env["DB_NAME"]]


def client(email):
    s = requests.Session()
    s.headers["Authorization"] = "Bearer " + subprocess.check_output(["python", "/app/tests/clerk_token.py", email], text=True).strip()
    return s


def restart_backend():
    subprocess.run(["sudo", "supervisorctl", "restart", "backend"], capture_output=True)
    end = time.time() + 60
    while time.time() < end:
        try:
            if requests.get(f"{BASE_URL}/api/status", timeout=5).status_code < 500:
                return
        except Exception:
            pass
        time.sleep(0.5)


def timed(s, method, path, **kw):
    t = time.time()
    r = s.request(method, f"{BASE_URL}{path}", timeout=90, **kw)
    return r, time.time() - t


@pytest.fixture(scope="module")
def A():
    return client(A_EMAIL)


@pytest.fixture(scope="module")
def B():
    return client(B_EMAIL)


@pytest.fixture(scope="module")
def uid_b(B):
    # B's user id: the user_settings row other than A's (look up via a target PUT to be safe)
    B.put(f"{BASE_URL}/api/target", json={"target": "cloud"})
    return None


# ---------- cold start: groups fast from DB, then prewarm makes state fast ----------
class TestColdStart:
    def test_groups_fast_after_restart(self, A):
        restart_backend()
        r, dt = timed(A, "GET", "/api/browser/groups")
        print(f"cold groups: {dt:.2f}s status={r.status_code}")
        assert r.status_code == 200, r.text
        d = r.json()
        assert dt < 1.5, f"groups took {dt:.2f}s"
        assert isinstance(d["groups"], list) and d["groups"]
        assert any(g["id"] == "1" for g in d["groups"])
        for g in d["groups"]:
            assert "run" in g and "name" in g and "tabs" in g
        TestColdStart.cold_ids = [g["id"] for g in d["groups"]]

    def test_prewarm_makes_state_fast(self, A):
        # give the background prewarm time to start chromium
        time.sleep(15)
        r, dt = timed(A, "GET", "/api/browser/state")
        print(f"state after prewarm: {dt:.2f}s")
        assert r.status_code == 200, r.text
        assert dt < 3, f"state took {dt:.2f}s even after prewarm"
        assert "tabs" in r.json()

    def test_live_groups_match_saved(self, A):
        r, dt = timed(A, "GET", "/api/browser/groups")
        print(f"warm groups: {dt:.2f}s")
        assert r.status_code == 200
        ids = [g["id"] for g in r.json()["groups"]]
        assert ids == TestColdStart.cold_ids, f"saved {TestColdStart.cold_ids} vs live {ids}"


# ---------- per-user lock: two users cold-start concurrently ----------
class TestPerUserLock:
    def test_concurrent_cold_starts_not_serialized(self, A, B):
        restart_backend()
        res = {}

        def go(name, s):
            r, dt = timed(s, "GET", "/api/browser/state")
            res[name] = (r.status_code, dt)

        ts = [threading.Thread(target=go, args=(n, s)) for n, s in (("A", A), ("B", B))]
        t0 = time.time()
        [t.start() for t in ts]
        [t.join() for t in ts]
        total = time.time() - t0
        print(f"concurrent: {res} total={total:.2f}")
        assert res["A"][0] == 200 and res["B"][0] == 200
        # baselines: each user's cold start alone
        single = {}
        for n, s in (("A", A), ("B", B)):
            restart_backend()
            single[n] = timed(s, "GET", "/api/browser/state")[1]
        print(f"single cold: {single}")
        # a global lock would make whichever user is queued second wait for the other's full launch;
        # the fast (1-workspace) user must finish well before the slow (multi-workspace) user
        fast, slow = sorted([res["A"][1], res["B"][1]])
        assert fast < slow * 0.6, f"looks serialized: concurrent={res} singles={single}"


# ---------- laptop target, helper offline ----------
class TestLaptopOffline:
    def test_groups_saved_or_default_when_helper_offline(self, B):
        t = B.get(f"{BASE_URL}/api/target").json()
        assert t["helper_online"] is False
        # find B's uid: the user_settings rows; the one whose cloud workspace only has Main and isn't A's
        a_uid = "user_3Lc1a7ouvhi20c6KxYFy1AAwtyj"
        b_uid = "user_3Lc2oBvUNT3bsqXThUco49EoosW"
        db.user_settings.update_one({"user_id": b_uid}, {"$set": {"target": "laptop"}})
        try:
            assert B.get(f"{BASE_URL}/api/target").json()["target"] == "laptop"
            r, dt = timed(B, "GET", "/api/browser/groups")
            print(f"laptop offline groups: {dt:.2f}s {r.status_code} {r.text[:200]}")
            assert r.status_code == 200, r.text
            gs = r.json()["groups"]
            assert gs[0]["id"] == "1" and gs[0]["name"] == "Main"
            # with saved laptop workspaces
            db.workspaces.insert_one({"user_id": b_uid, "target": "laptop", "TEST_": True, "groups": [
                {"id": "1", "name": "Main", "label": "", "url": "", "tabs": 1, "urls": ["https://example.com"], "active": 0},
                {"id": "TESTlap1", "name": "TEST_laptop_ws", "label": "", "url": "", "tabs": 1, "urls": ["https://example.org"], "active": 0}]})
            r = B.get(f"{BASE_URL}/api/browser/groups")
            assert r.status_code == 200
            names = [g["name"] for g in r.json()["groups"]]
            assert "TEST_laptop_ws" in names, names
            # actions still require helper -> 409
            r2 = B.get(f"{BASE_URL}/api/browser/state")
            print("laptop offline state:", r2.status_code)
            assert r2.status_code == 409
        finally:
            db.workspaces.delete_one({"user_id": b_uid, "target": "laptop", "TEST_": True})
            db.user_settings.update_one({"user_id": b_uid}, {"$set": {"target": "cloud"}})
        assert B.get(f"{BASE_URL}/api/target").json()["target"] == "cloud"


# ---------- workspace CRUD regression ----------
class TestWorkspaceCRUD:
    def test_create_rename_close(self, B):
        r = B.post(f"{BASE_URL}/api/browser/groups", json={"name": "TEST_ws19", "url": "https://example.com"})
        assert r.status_code == 200, r.text
        gid = r.json()["id"]
        try:
            gs = B.get(f"{BASE_URL}/api/browser/groups").json()["groups"]
            assert any(g["id"] == gid and g["name"] == "TEST_ws19" for g in gs)
            r = B.put(f"{BASE_URL}/api/browser/groups/{gid}", json={"name": "TEST_ws19_renamed"})
            assert r.status_code == 200, r.text
            gs = B.get(f"{BASE_URL}/api/browser/groups").json()["groups"]
            assert any(g["id"] == gid and g["name"] == "TEST_ws19_renamed" for g in gs)
            # persisted to DB
            time.sleep(1)
            doc = db.workspaces.find_one({"user_id": "user_3Lc2oBvUNT3bsqXThUco49EoosW", "target": "cloud"})
            assert any(g["id"] == gid and g["name"] == "TEST_ws19_renamed" for g in doc["groups"])
        finally:
            r = B.delete(f"{BASE_URL}/api/browser/groups/{gid}")
            assert r.status_code == 200, r.text
        gs = B.get(f"{BASE_URL}/api/browser/groups").json()["groups"]
        assert not any(g["id"] == gid for g in gs)

    def test_unauth_401(self):
        assert requests.get(f"{BASE_URL}/api/browser/groups").status_code in (401, 403)
