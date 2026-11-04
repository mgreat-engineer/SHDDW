# Shadow iteration-4: schedules CRUD/validation, cron endpoint + due logic, preview (dry run), results table + xlsx export, helper update tracking
# Run serially: cd /app/backend && pytest tests/test_iter4_features.py -n 0 -v -s
import io
import os
import subprocess
import time
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient

BASE_URL = dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"].rstrip("/")
_BE = dotenv_values("/app/backend/.env")
SECRET = _BE["WEBHOOK_CRON_SECRET"]
DB = MongoClient(_BE["MONGO_URL"])[_BE["DB_NAME"]]
A_EMAIL = "shadow.a+clerk_test@example.com"
B_EMAIL = "shadow.b+clerk_test@example.com"
PY = "/root/.venv/bin/python"
BUILD_INFO = "/app/desktop/shadow_helper/build_info.json"


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


@pytest.fixture(scope="module")
def skill(A):
    r = A.post(f"{BASE_URL}/api/skills", json={"name": "TEST_sched_skill", "description": "test", "steps": ["Open https://example.com"]})
    assert r.status_code == 200
    sk = r.json()
    yield sk
    A.delete(f"{BASE_URL}/api/skills/{sk['id']}")


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


def cron(auth="ok", wid=None):
    h = {}
    if auth == "ok":
        h["Authorization"] = f"Bearer {SECRET}"
    elif auth:
        h["Authorization"] = auth
    if wid:
        h["X-Webhook-Id"] = wid
    return requests.post(f"{BASE_URL}/api/cron/schedules", headers=h, json={}, timeout=10)


def sched_body(skill_id, **kw):
    return {"skill_id": skill_id, "days": [1, 2, 3, 4, 5], "time": "08:00", "timezone": "America/New_York",
            "target": "laptop", "instructions": "", "enabled": True, **kw}


def online(s):
    return s.get(f"{BASE_URL}/api/target").json()["helper_online"]


def wait_online(s, want=True, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        if online(s) == want:
            return True
        time.sleep(1.5)
    return False


def kill_helper():
    subprocess.run(["pkill", "-9", "-f", "helper_sim.py"], capture_output=True)
    subprocess.run(["pkill", "-9", "-f", "helperhome"], capture_output=True)


def start_helper():
    env = {**os.environ, "SHADOW_CHROME_PATH": "/usr/bin/google-chrome"}
    subprocess.Popen(f"setsid nohup {PY} /app/tests/helper_sim.py >> /tmp/helper.log 2>&1 < /dev/null &", shell=True, cwd="/app", env=env)


# ---------------- Schedules CRUD ----------------
class TestSchedules:
    def test_validation(self, A, skill):
        u = f"{BASE_URL}/api/schedules"
        assert A.post(u, json=sched_body(skill["id"], days=[])).status_code == 400
        assert A.post(u, json=sched_body(skill["id"], days=[7])).status_code == 400
        assert A.post(u, json=sched_body(skill["id"], time="08:07")).status_code == 400
        assert A.post(u, json=sched_body(skill["id"], time="24:00")).status_code == 400
        assert A.post(u, json=sched_body(skill["id"], timezone="Mars/Olympus")).status_code == 400
        assert A.post(u, json=sched_body(skill["id"], target="moon")).status_code == 400
        assert A.post(u, json=sched_body(str(uuid.uuid4()))).status_code == 404
        assert requests.get(u).status_code == 401

    def test_create_next_run_and_update(self, A, B, skill):
        r = A.post(f"{BASE_URL}/api/schedules", json=sched_body(skill["id"], days=[3, 1, 1], time="08:15", timezone="Asia/Kolkata"))
        assert r.status_code == 200, r.text
        sc = r.json()
        assert "_id" not in sc and sc["days"] == [1, 3] and sc["skill_name"] == "TEST_sched_skill"
        nxt = datetime.fromisoformat(sc["next_run_at"])
        assert nxt > datetime.now(timezone.utc) and nxt < datetime.now(timezone.utc) + timedelta(days=7, minutes=1)
        loc = nxt.astimezone(ZoneInfo("Asia/Kolkata"))
        assert (loc.hour, loc.minute) == (8, 15) and loc.isoweekday() % 7 in (1, 3)
        assert nxt.utcoffset() == timedelta(0)
        # list + isolation
        assert any(x["id"] == sc["id"] for x in A.get(f"{BASE_URL}/api/schedules").json())
        assert not any(x["id"] == sc["id"] for x in B.get(f"{BASE_URL}/api/schedules").json())
        assert B.put(f"{BASE_URL}/api/schedules/{sc['id']}", json=sched_body(skill["id"])).status_code in (404,)
        assert B.delete(f"{BASE_URL}/api/schedules/{sc['id']}").status_code == 404
        # disable -> null
        r = A.put(f"{BASE_URL}/api/schedules/{sc['id']}", json=sched_body(skill["id"], enabled=False))
        assert r.status_code == 200 and r.json()["enabled"] is False and r.json()["next_run_at"] is None
        # re-enable with DST zone (all days) -> next within 24h at local 23:45
        r = A.put(f"{BASE_URL}/api/schedules/{sc['id']}", json=sched_body(skill["id"], days=list(range(7)), time="23:45", timezone="America/Los_Angeles"))
        n2 = datetime.fromisoformat(r.json()["next_run_at"])
        l2 = n2.astimezone(ZoneInfo("America/Los_Angeles"))
        assert (l2.hour, l2.minute) == (23, 45) and n2 - datetime.now(timezone.utc) <= timedelta(hours=24)
        got = [x for x in A.get(f"{BASE_URL}/api/schedules").json() if x["id"] == sc["id"]][0]
        assert got["time"] == "23:45" and got["timezone"] == "America/Los_Angeles"
        assert A.delete(f"{BASE_URL}/api/schedules/{sc['id']}").status_code == 200
        assert A.delete(f"{BASE_URL}/api/schedules/{sc['id']}").status_code == 404

    def test_delete_skill_deletes_schedules(self, A):
        sk = A.post(f"{BASE_URL}/api/skills", json={"name": "TEST_tmp_skill", "steps": ["x"]}).json()
        sc = A.post(f"{BASE_URL}/api/schedules", json=sched_body(sk["id"])).json()
        assert A.delete(f"{BASE_URL}/api/skills/{sk['id']}").status_code == 200
        assert not any(x["id"] == sc["id"] for x in A.get(f"{BASE_URL}/api/schedules").json())
        assert DB.schedules.count_documents({"id": sc["id"]}) == 0


# ---------------- Cron ----------------
class TestCron:
    def test_auth(self):
        assert cron(auth=None).status_code == 401
        assert cron(auth="Bearer wrong").status_code == 401
        assert cron(auth=SECRET).status_code == 401  # missing Bearer prefix

    def test_ok_and_duplicate(self):
        wid = f"TEST_{uuid.uuid4()}"
        t = time.time()
        r = cron(wid=wid)
        assert r.status_code == 200 and r.json() == {"ok": True}
        assert time.time() - t < 5
        r2 = cron(wid=wid)
        assert r2.status_code == 200 and r2.json().get("duplicate") is True

    def test_due_laptop_then_skipped(self, A, skill):
        stop_active(A)
        assert online(A), "helper sim must be online for this test"
        s1 = A.post(f"{BASE_URL}/api/schedules", json=sched_body(skill["id"], days=list(range(7)), instructions="Then finish.")).json()
        s2 = A.post(f"{BASE_URL}/api/schedules", json=sched_body(skill["id"], days=list(range(7)), target="cloud")).json()
        try:
            past = (datetime.now(timezone.utc) - timedelta(minutes=5)).replace(microsecond=0).isoformat()
            DB.schedules.update_one({"id": s1["id"]}, {"$set": {"next_run_at": past}})
            assert cron().status_code == 200
            time.sleep(6)
            d1 = DB.schedules.find_one({"id": s1["id"]}, {"_id": 0})
            print("s1 after cron:", {k: d1.get(k) for k in ("last_status", "last_run_id", "last_note", "next_run_at")})
            assert d1["last_status"] == "started" and d1["last_run_id"]
            assert d1["next_run_at"] > datetime.now(timezone.utc).isoformat() and d1["last_note"] == ""
            run = A.get(f"{BASE_URL}/api/runs/{d1['last_run_id']}").json()
            assert run["trigger"] == "schedule" and run["schedule_id"] == s1["id"] and run["target"] == "laptop"
            assert run["goal"].startswith('Run skill "TEST_sched_skill"') and "Then finish." in run["goal"]
            # second schedule while run1 active -> skipped
            if A.get(f"{BASE_URL}/api/runs/active").json().get("run"):
                DB.schedules.update_one({"id": s2["id"]}, {"$set": {"next_run_at": past}})
                assert cron().status_code == 200
                time.sleep(5)
                d2 = DB.schedules.find_one({"id": s2["id"]}, {"_id": 0})
                print("s2 after cron:", {k: d2.get(k) for k in ("last_status", "last_note", "next_run_at")})
                assert d2["last_status"] == "skipped" and "already in progress" in d2["last_note"]
                assert d2["next_run_at"] > past
            else:
                pytest.skip("run1 finished too fast to check skipped")
        finally:
            stop_active(A)
            A.delete(f"{BASE_URL}/api/schedules/{s1['id']}")
            A.delete(f"{BASE_URL}/api/schedules/{s2['id']}")

    def test_offline_falls_back_to_cloud_and_update_tracking(self, A, skill):
        """Kill helper -> due laptop schedule runs on cloud. Then restart helper with build_info 1.0.5 -> last_update recorded."""
        stop_active(A)
        sc = A.post(f"{BASE_URL}/api/schedules", json=sched_body(skill["id"], days=list(range(7)))).json()
        try:
            kill_helper()
            assert wait_online(A, False)
            past = (datetime.now(timezone.utc) - timedelta(minutes=1)).replace(microsecond=0).isoformat()
            DB.schedules.update_one({"id": sc["id"]}, {"$set": {"next_run_at": past}})
            assert cron().status_code == 200
            time.sleep(8)
            d = DB.schedules.find_one({"id": sc["id"]}, {"_id": 0})
            print("offline sched:", {k: d.get(k) for k in ("last_status", "last_note", "last_run_id")})
            assert d["last_status"] == "started" and "offline" in d["last_note"].lower()
            run = A.get(f"{BASE_URL}/api/runs/{d['last_run_id']}").json()
            assert run["target"] == "cloud" and run["trigger"] == "schedule"
        finally:
            stop_active(A)
            A.delete(f"{BASE_URL}/api/schedules/{sc['id']}")
            with open(BUILD_INFO, "w") as f:
                f.write('{"version":"1.0.5","repo":""}')
            start_helper()
        assert wait_online(A, True, 90)
        time.sleep(3)
        t = A.get(f"{BASE_URL}/api/target").json()
        print("target helper:", t["helper"])
        assert t["helper"]["info"]["version"] == "1.0.5"
        assert t["helper"]["last_update"]["to"] == "1.0.5" and t["helper"]["last_update"]["from"]
        devs = A.get(f"{BASE_URL}/api/devices").json()
        on = [d for d in devs if d["online"]][0]
        assert on["last_update"]["to"] == "1.0.5" and on["update_history"][0]["to"] == "1.0.5"
        assert on["info"]["version"] == "1.0.5"


# ---------------- Results trimming / export (seeded run doc, no GPT) ----------------
class TestResultsApi:
    def test_trim_and_export(self, A, B, skill):
        uid = DB.skills.find_one({"id": skill["id"]})["user_id"]
        rid = f"TEST_{uuid.uuid4()}"
        rows = [{"n": str(i), "v": f"val{i}"} for i in range(150)]
        now = datetime.now(timezone.utc).isoformat()
        DB.runs.insert_one({"id": rid, "user_id": uid, "goal": "TEST_trim", "status": "completed", "created_at": now, "updated_at": now,
                            "tables": [{"name": "TEST/tbl:1", "columns": ["n", "v"], "rows": rows}], "plan": [], "step_count": 0})
        rid2 = f"TEST_{uuid.uuid4()}"
        DB.runs.insert_one({"id": rid2, "user_id": uid, "goal": "TEST_empty", "status": "completed", "created_at": now, "updated_at": now,
                            "tables": [], "plan": [], "step_count": 0})
        try:
            r = A.get(f"{BASE_URL}/api/runs/{rid}").json()
            t = r["tables"][0]
            assert t["row_count"] == 150 and len(t["rows"]) == 100 and t["rows"][0]["n"] == "50" and t["rows"][-1]["n"] == "149"
            assert "_id" not in r
            assert all("tables" not in x for x in A.get(f"{BASE_URL}/api/runs").json())
            ex = A.get(f"{BASE_URL}/api/runs/{rid}/export")
            assert ex.status_code == 200 and "spreadsheetml" in ex.headers["content-type"] and "attachment" in ex.headers["content-disposition"]
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(ex.content))
            ws = wb.worksheets[0]
            assert ws.max_row == 151 and [c.value for c in ws[1]] == ["n", "v"]
            assert A.get(f"{BASE_URL}/api/runs/{rid2}/export").status_code == 404
            assert B.get(f"{BASE_URL}/api/runs/{rid}/export").status_code == 404
        finally:
            DB.runs.delete_many({"id": {"$in": [rid, rid2]}})


# ---------------- Preview + results (GPT) ----------------
class TestGptFlows:
    def test_preview_requires_skill(self, A):
        stop_active(A)
        assert A.post(f"{BASE_URL}/api/runs", json={"mode": "preview", "command": "x"}).status_code == 400

    def test_preview_run(self, A):
        stop_active(A)
        sk = [s for s in A.get(f"{BASE_URL}/api/skills").json() if s["name"].lower().startswith("example learn more")]
        if not sk:
            pytest.skip("Example learn more skill missing")
        r = A.post(f"{BASE_URL}/api/runs", json={"skill_id": sk[0]["id"], "mode": "preview"})
        assert r.status_code == 200, r.text
        run = r.json()
        assert run["mode"] == "preview" and run["goal"].startswith("Preview skill")
        run = wait_run(A, run["id"], ["completed", "failed", "awaiting_approval", "waiting_input", "stopped"])
        print("preview status", run["status"], run.get("summary"))
        for st in sorted(run["steps"], key=lambda x: x["idx"]):
            print(st["idx"], st.get("action"), st.get("simulated"), str(st.get("result"))[:100])
        assert run["status"] == "completed"
        sim = [s for s in run["steps"] if s.get("simulated")]
        assert sim and all(str(s["result"]).startswith("PREVIEW — not done. Would") for s in sim)
        assert any(s.get("action") in ("click", "type_text", "press_key") for s in sim)
        assert not any(s.get("action") in ("click", "type_text", "press_key") and not s.get("simulated") for s in run["steps"])
        assert A.get(f"{BASE_URL}/api/runs/{run['id']}/export").status_code == 404
        pytest.preview_run_id = run["id"]

    def test_results_table_run(self, A):
        stop_active(A)
        r = A.post(f"{BASE_URL}/api/runs", json={"command": "Go to https://www.iana.org/domains/reserved and collect the reserved domains and purposes into a results table"})
        assert r.status_code == 200, r.text
        run = wait_run(A, r.json()["id"], ["completed", "failed", "awaiting_approval", "waiting_input", "stopped"], 300)
        print("results status", run["status"], run.get("summary"))
        stop_active(A)
        assert run["tables"], "no tables"
        t = run["tables"][0]
        print("table", t["name"], t["columns"], t["row_count"])
        assert t["row_count"] >= 3 and len(t["columns"]) >= 2
        ex = A.get(f"{BASE_URL}/api/runs/{run['id']}/export")
        assert ex.status_code == 200 and ex.content[:2] == b"PK"
        pytest.results_run_id = run["id"]
