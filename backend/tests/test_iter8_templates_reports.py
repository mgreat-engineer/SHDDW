# Shadow iteration-8: workspace templates (CRUD, isolation, from-workspace, open -> fresh workspace w/o cookies, skill autostart, 409 at max)
# and daily report (grouping by client label, buckets, tz boundaries, validation).
# Run serially: cd /app/backend && pytest tests/test_iter8_templates_reports.py -n 0 -v -s
import subprocess
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
import requests
from dotenv import dotenv_values

BASE_URL = dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
A_EMAIL = "shadow.a+clerk_test@example.com"
B_EMAIL = "shadow.b+clerk_test@example.com"
SLOW = "open example.com, then wait 20 seconds, then tell me the page title"


def token(email):
    return subprocess.check_output(["python", "/app/tests/clerk_token.py", email], text=True).strip()


def sess(email):
    s = requests.Session()
    s.headers["Authorization"] = "Bearer " + token(email)
    return s


@pytest.fixture(scope="module")
def A():
    return sess(A_EMAIL)


@pytest.fixture(scope="module")
def B():
    return sess(B_EMAIL)


@pytest.fixture(scope="module")
def created(A):
    c = {"tpl": [], "ws": [], "runs": [], "skills": []}
    yield c
    for r in c["runs"]:
        A.post(f"{API}/runs/{r}/stop", timeout=30)
    time.sleep(1)
    for t in c["tpl"]:
        A.delete(f"{API}/templates/{t}", timeout=30)
    for g in c["ws"]:
        A.delete(f"{API}/browser/groups/{g}", timeout=60)
    for s in c["skills"]:
        A.delete(f"{API}/skills/{s}", timeout=30)


def groups(A):
    r = A.get(f"{API}/browser/groups", timeout=90)
    assert r.status_code == 200, r.text
    return {g["id"]: g for g in r.json()["groups"]}


def new_ws(A, created, **body):
    r = A.post(f"{API}/browser/groups", json=body, timeout=90)
    assert r.status_code == 200, r.text
    created["ws"].append(r.json()["id"])
    return r.json()


def nav(A, gid, url):
    r = A.post(f"{API}/browser/navigate", params={"group": gid}, json={"url": url}, timeout=60)
    assert r.status_code == 200, r.text


def mk_tpl(A, created, **body):
    r = A.post(f"{API}/templates", json=body, timeout=30)
    assert r.status_code == 200, r.text
    created["tpl"].append(r.json()["id"])
    return r.json()


def wait_status(A, rid, ok=("completed", "failed", "stopped", "waiting_input"), timeout=150):
    end = time.time() + timeout
    while time.time() < end:
        run = A.get(f"{API}/runs/{rid}", timeout=30).json()
        if run["status"] in ok:
            return run
        time.sleep(3)
    return run


# ---- templates CRUD + validation
class TestTemplateCRUD:
    def test_crud(self, A, created):
        t = mk_tpl(A, created, name="  TEST_tpl1  ", label="TEST Client", urls=["https://example.com", "about:blank", "data:text/html,x", " ", "https://httpbin.org/get"])
        assert t["name"] == "TEST_tpl1" and t["label"] == "TEST Client"
        assert t["urls"] == ["https://example.com", "https://httpbin.org/get"]
        assert t["skill_id"] is None and isinstance(t["id"], str)
        lst = A.get(f"{API}/templates").json()
        assert any(x["id"] == t["id"] for x in lst) and all("_id" not in x for x in lst)
        u = A.put(f"{API}/templates/{t['id']}", json={"name": "TEST_tpl1b", "label": "TEST Other", "urls": ["https://example.org"]})
        assert u.status_code == 200, u.text
        assert u.json()["name"] == "TEST_tpl1b" and u.json()["urls"] == ["https://example.org"]
        got = [x for x in A.get(f"{API}/templates").json() if x["id"] == t["id"]][0]
        assert got["label"] == "TEST Other"
        d = A.delete(f"{API}/templates/{t['id']}")
        assert d.status_code == 200
        assert A.delete(f"{API}/templates/{t['id']}").status_code == 404
        assert not any(x["id"] == t["id"] for x in A.get(f"{API}/templates").json())

    def test_validation(self, A, created):
        assert A.post(f"{API}/templates", json={"name": "  ", "urls": []}).status_code == 400
        assert A.post(f"{API}/templates", json={"urls": []}).status_code == 422
        assert A.post(f"{API}/templates", json={"name": "TEST_x", "skill_id": "nope"}).status_code == 404
        assert A.put(f"{API}/templates/does-not-exist", json={"name": "x"}).status_code == 404
        assert A.post(f"{API}/templates/does-not-exist/open").status_code == 404

    def test_isolation(self, A, B, created):
        t = mk_tpl(A, created, name="TEST_iso", urls=["https://example.com"])
        assert not any(x["id"] == t["id"] for x in B.get(f"{API}/templates").json())
        assert B.put(f"{API}/templates/{t['id']}", json={"name": "hack"}).status_code == 404
        assert B.delete(f"{API}/templates/{t['id']}").status_code == 404
        assert B.post(f"{API}/templates/{t['id']}/open").status_code == 404
        got = [x for x in A.get(f"{API}/templates").json() if x["id"] == t["id"]][0]
        assert got["name"] == "TEST_iso"

    def test_unauth(self):
        assert requests.get(f"{API}/templates").status_code == 401
        assert requests.get(f"{API}/reports/daily", params={"date": "2026-01-01"}).status_code == 401


# ---- from-workspace + open (fresh, no cookies)
class TestTemplateOpen:
    def test_from_ws_and_open_no_cookies(self, A, created):
        src = new_ws(A, created, name="TEST_src", label="TEST Src Client", url="https://example.com")
        nav(A, src["id"], "https://httpbin.org/cookies/set?tpl=1")
        r = A.post(f"{API}/browser/tabs", params={"group": src["id"]}, json={"action": "new", "url": "https://httpbin.org/cookies"}, timeout=60)
        assert r.status_code == 200, r.text
        time.sleep(1)
        f = A.post(f"{API}/templates/from-workspace", json={"group_id": src["id"]}, timeout=60)
        assert f.status_code == 200, f.text
        t = f.json()
        created["tpl"].append(t["id"])
        print("from-ws template:", t)
        assert t["name"] == "TEST_src" and t["label"] == "TEST Src Client"
        assert any("httpbin.org/cookies" in u for u in t["urls"])
        named = A.post(f"{API}/templates/from-workspace", json={"group_id": src["id"], "name": "TEST_named"}, timeout=60)
        assert named.status_code == 200 and named.json()["name"] == "TEST_named"
        created["tpl"].append(named.json()["id"])
        # open
        tc = mk_tpl(A, created, name="TEST_ck", label="TEST Src Client", urls=["https://httpbin.org/cookies"])
        o = A.post(f"{API}/templates/{tc['id']}/open", timeout=90)
        assert o.status_code == 200, o.text
        out = o.json()
        g = out["group"]
        created["ws"].append(g["id"])
        assert g["id"] != src["id"] and g["name"] == "TEST_ck" and g["label"] == "TEST Src Client"
        assert out["run"] is None and out["run_error"] is None
        assert any("httpbin.org/cookies" in u for u in g["urls"])
        assert g["id"] in groups(A)
        time.sleep(1.5)
        fr = A.get(f"{API}/browser/frame", params={"group": g["id"], "quality": 80}, timeout=30)
        open("/tmp/tpl_open_cookies.jpg", "wb").write(fr.content)
        fr = A.get(f"{API}/browser/frame", params={"group": src["id"], "quality": 80}, timeout=30)
        open("/tmp/tpl_src_cookies.jpg", "wb").write(fr.content)
        # Cookie check through the page text via a cheap DOM read is not exposed; frames saved for visual check

    def test_from_ws_unknown_group(self, A):
        r = A.post(f"{API}/templates/from-workspace", json={"group_id": "zzzz9999"}, timeout=60)
        print("from-ws unknown:", r.status_code, r.text[:200])
        assert r.status_code in (400, 404)

    def test_open_with_skill_starts_run(self, A, created):
        sk = A.post(f"{API}/skills", json={"name": "TEST_title_skill", "description": "Tell the page title",
                                           "steps": ["Do not browse. Tell me the title of the current page and finish."]})
        assert sk.status_code == 200
        created["skills"].append(sk.json()["id"])
        t = mk_tpl(A, created, name="TEST_sk", label="TEST Skill Client", urls=["https://example.com"], skill_id=sk.json()["id"], instructions="Keep it short")
        assert t["skill_name"] == "TEST_title_skill" and t["instructions"] == "Keep it short"
        o = A.post(f"{API}/templates/{t['id']}/open", timeout=90)
        assert o.status_code == 200, o.text
        out = o.json()
        created["ws"].append(out["group"]["id"])
        print("open-with-skill:", out["run_error"], (out["run"] or {}).get("goal"))
        assert out["run_error"] is None and out["run"]
        run = out["run"]
        created["runs"].append(run["id"])
        assert run["group_id"] == out["group"]["id"]
        assert run["workspace_name"] == "TEST_sk" and run["workspace_label"] == "TEST Skill Client"
        d = wait_status(A, run["id"])
        print("skill run:", d["status"], d.get("summary"))
        assert d["status"] in ("completed", "waiting_input")


# ---- daily report
class TestDailyReport:
    def test_validation(self, A):
        assert A.get(f"{API}/reports/daily", params={"date": "2026-1-1"}).status_code == 422
        assert A.get(f"{API}/reports/daily").status_code == 422
        assert A.get(f"{API}/reports/daily", params={"date": "2026-13-40"}).status_code == 400
        assert A.get(f"{API}/reports/daily", params={"date": "2026-01-01", "tz": "Mars/Base"}).status_code == 400

    def test_grouping_buckets_tz(self, A, created):
        g = new_ws(A, created, name="TEST_rep", label="AAA TEST Report Client")["id"]
        r = A.post(f"{API}/runs", params={"group": g}, json={"command": SLOW}, timeout=60)
        assert r.status_code == 200, r.text
        rid = r.json()["id"]
        created["runs"].append(rid)
        assert r.json()["workspace_name"] == "TEST_rep" and r.json()["workspace_label"] == "AAA TEST Report Client"
        time.sleep(3)
        assert A.post(f"{API}/runs/{rid}/pause", timeout=30).status_code == 200
        created_at = datetime.fromisoformat(r.json()["created_at"])

        def report(tz):
            day = created_at.astimezone(ZoneInfo(tz)).date().isoformat()
            x = A.get(f"{API}/reports/daily", params={"date": day, "tz": tz}, timeout=30)
            assert x.status_code == 200, x.text
            return day, x.json()

        day, rep = report("UTC")
        assert rep["date"] == day and rep["tz"] == "UTC"
        labels = [c["label"] for c in rep["clients"]]
        print("labels:", labels, "totals:", rep["totals"], "total:", rep["total"])
        if "No client set" in labels:
            assert labels[-1] == "No client set"
        c = [c for c in rep["clients"] if c["label"] == "AAA TEST Report Client"][0]
        assert "TEST_rep" in c["workspaces"]
        mine = [x for x in c["runs"] if x["id"] == rid][0]
        assert mine["status"] == "paused" and c["counts"].get("needs_you", 0) >= 1
        assert rep["total"] == sum(rep["totals"].values()) == sum(len(c["runs"]) for c in rep["clients"])
        assert set(rep["totals"]) <= {"completed", "needs_you", "running", "failed", "stopped"}
        # tz: run appears on its local date in far-east and far-west zones, not the previous day
        for tz in ("Pacific/Kiritimati", "Pacific/Pago_Pago", "Asia/Kolkata"):
            d, rp = report(tz)
            assert any(x["id"] == rid for cc in rp["clients"] for x in cc["runs"]), tz
            prev = (datetime.fromisoformat(d) - timedelta(days=1)).date().isoformat()
            rp2 = A.get(f"{API}/reports/daily", params={"date": prev, "tz": tz}).json()
            assert not any(x["id"] == rid for cc in rp2["clients"] for x in cc["runs"]), tz
        # stop -> stopped bucket
        assert A.post(f"{API}/runs/{rid}/stop", timeout=30).status_code == 200
        _, rep = report("UTC")
        c = [c for c in rep["clients"] if c["label"] == "AAA TEST Report Client"][0]
        assert [x for x in c["runs"] if x["id"] == rid][0]["status"] == "stopped" and c["counts"].get("stopped") == 1

    def test_empty_day(self, A):
        r = A.get(f"{API}/reports/daily", params={"date": "2001-01-01", "tz": "UTC"})
        assert r.status_code == 200 and r.json()["total"] == 0 and r.json()["clients"] == [] and r.json()["totals"] == {}


# ---- max workspaces -> 409 on open
class TestMax:
    def test_open_at_max_409(self, A, created):
        t = mk_tpl(A, created, name="TEST_max", urls=["https://example.com"])
        extra = []
        try:
            while len(groups(A)) < 10:
                r = A.post(f"{API}/browser/groups", json={"name": "TEST_fill", "url": "about:blank"}, timeout=90)
                assert r.status_code == 200, r.text
                extra.append(r.json()["id"])
            o = A.post(f"{API}/templates/{t['id']}/open", timeout=60)
            print("open at max:", o.status_code, o.text[:200])
            assert o.status_code == 409
        finally:
            for g in extra:
                A.delete(f"{API}/browser/groups/{g}", timeout=60)
