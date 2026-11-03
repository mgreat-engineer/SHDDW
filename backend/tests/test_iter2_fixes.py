# Shadow iteration-2 retest: dialog robustness, stale events, agent confirm click, reject => blocked_risks
# Run serially: pytest /app/backend/tests/test_iter2_fixes.py -n 0 -v -s
import subprocess
import threading
import time
import urllib.parse

import pytest
import requests
from dotenv import dotenv_values

BASE_URL = dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"].rstrip("/")
A_EMAIL = "shadow.a+clerk_test@example.com"
CONFIRM_HTML = "data:text/html," + urllib.parse.quote(
    "<title>Start</title><button style='width:400px;height:200px' "
    "onclick=\"document.title=confirm('Sure?')?'ACCEPTED':'DISMISSED'\">Go</button>")


@pytest.fixture(scope="module")
def A():
    s = requests.Session()
    s.headers["Authorization"] = "Bearer " + subprocess.check_output(["python", "/app/tests/clerk_token.py", A_EMAIL], text=True).strip()
    return s


def stop_active(s):
    r = s.get(f"{BASE_URL}/api/runs/active").json()
    if r.get("run"):
        s.post(f"{BASE_URL}/api/runs/{r['run']['id']}/stop")
        time.sleep(2)


def wait_run(s, rid, until, timeout=200):
    end = time.time() + timeout
    run = None
    while time.time() < end:
        run = s.get(f"{BASE_URL}/api/runs/{rid}").json()
        if run["status"] in until:
            return run
        time.sleep(3)
    return run


def open_confirm(A):
    assert A.post(f"{BASE_URL}/api/browser/navigate", json={"url": CONFIRM_HTML}).status_code == 200
    t0 = time.time()
    r = A.post(f"{BASE_URL}/api/browser/input", json={"kind": "click", "x": 100, "y": 50}, timeout=40)
    return r, time.time() - t0


# ---- Manual dialog fixes (no GPT) ----
class TestDialogs:
    def test_dialog_absent_400(self, A):
        stop_active(A)
        A.post(f"{BASE_URL}/api/browser/navigate", json={"url": "https://example.com"})
        r = A.post(f"{BASE_URL}/api/browser/dialog", json={"accept": True})
        assert r.status_code == 400, r.text

    def test_click_opening_confirm_returns_fast_and_input_409(self, A):
        r, dt = open_confirm(A)
        print("input click", r.status_code, r.text, f"{dt:.1f}s")
        assert r.status_code == 200 and dt < 8
        st = A.get(f"{BASE_URL}/api/browser/state").json()
        assert st["dialog"] and st["dialog"]["type"] == "confirm"
        r2 = A.post(f"{BASE_URL}/api/browser/input", json={"kind": "click", "x": 100, "y": 50}, timeout=30)
        print("input while dialog", r2.status_code, r2.text)
        assert r2.status_code == 409
        assert A.post(f"{BASE_URL}/api/browser/dialog", json={"accept": True}).status_code == 200
        time.sleep(1)
        st = A.get(f"{BASE_URL}/api/browser/state").json()
        assert st["dialog"] is None
        assert [t for t in st["tabs"] if t["active"]][0]["title"] == "ACCEPTED"

    def test_dialog_cleared_after_navigation_and_stale_400(self, A):
        r, _ = open_confirm(A)
        assert r.status_code == 200
        assert A.get(f"{BASE_URL}/api/browser/state").json()["dialog"]
        t0 = time.time()
        n = A.post(f"{BASE_URL}/api/browser/navigate", json={"url": "https://example.com"}, timeout=60)
        print("navigate while dialog", n.status_code, n.text[:200], f"{time.time() - t0:.1f}s")
        time.sleep(1.5)
        st = A.get(f"{BASE_URL}/api/browser/state").json()
        print("state after nav", st["dialog"], st["tabs"])
        assert st["dialog"] is None
        r = A.post(f"{BASE_URL}/api/browser/dialog", json={"accept": True})
        print("dialog after nav", r.status_code, r.text)
        assert r.status_code == 400


# ---- Agent (GPT) ----
class TestAgent:
    def test_agent_confirm_and_no_stale_events(self, A):
        stop_active(A)
        # create a stale manual 'Dialog appeared' event first
        r, _ = open_confirm(A)
        assert r.status_code == 200
        A.post(f"{BASE_URL}/api/browser/dialog", json={"accept": False})
        cmd = ("Open data:text/html,<button onclick=\"document.title=confirm('Sure?')\">Go</button> , click Go, "
               "accept the dialog and report the page title")
        rid = A.post(f"{BASE_URL}/api/runs", json={"command": cmd}).json()["id"]
        run = wait_run(A, rid, ("completed", "failed", "stopped", "awaiting_approval", "waiting_input"), 180)
        steps = sorted(run["steps"], key=lambda s: s["idx"])
        for s in steps:
            print(s["idx"], s["action"], s["args"], s["ok"], s["result"][:160])
        print("final", run["status"], run.get("summary"), run.get("pending"))
        if run["status"] not in ("completed", "failed", "stopped"):
            A.post(f"{BASE_URL}/api/runs/{rid}/stop")
        assert steps and steps[0]["action"] != "handle_dialog"
        clicks = [s for s in steps if s["action"] in ("click", "click_at")]
        assert any("opened a confirm dialog" in s["result"] and s["ok"] for s in clicks)
        hd = [s for s in steps if s["action"] == "handle_dialog"]
        assert any(s["ok"] for s in hd)
        # title is 'true' (new page) or 'ACCEPTED' (agent reused the already-open confirm page)
        summ = (run.get("summary") or "").lower()
        assert run["status"] == "completed" and ("true" in summ or "accepted" in summ)

    def test_reject_send_blocks_other_routes(self, A):
        stop_active(A)
        saved = [p for p in A.get(f"{BASE_URL}/api/permissions").json() if p["category"] == "send"]
        for p in saved:
            A.delete(f"{BASE_URL}/api/permissions/{p['id']}")
        try:
            rid = A.post(f"{BASE_URL}/api/runs", json={"command": "Go to https://httpbin.org/forms/post, fill customer name TEST_Bob, and submit the order"}).json()["id"]
            run = wait_run(A, rid, ("awaiting_approval", "completed", "failed", "stopped", "waiting_input"), 200)
            print("first", run["status"], run.get("pending"))
            assert run["status"] == "awaiting_approval" and run["pending"]["risk"] == "send"
            n_before = run["step_count"]
            assert A.post(f"{BASE_URL}/api/runs/{rid}/approval", json={"decision": "reject"}).status_code == 200
            run = wait_run(A, rid, ("awaiting_approval", "completed", "failed", "stopped", "waiting_input"), 200)
            steps = sorted(run["steps"], key=lambda s: s["idx"])
            for s in steps:
                print(s["idx"], s["action"], s["args"], s["ok"], s["result"][:160])
            print("final", run["status"], run.get("summary"), run.get("pending"), run.get("blocked_risks"))
            if run["status"] not in ("completed", "failed", "stopped"):
                A.post(f"{BASE_URL}/api/runs/{rid}/stop")
            assert "send" in (run.get("blocked_risks") or [])
            assert not (run["status"] == "awaiting_approval" and (run.get("pending") or {}).get("risk") == "send")
            assert run["status"] in ("completed", "failed", "waiting_input")
            later = [s for s in steps if s["idx"] > n_before]
            blocked = [s for s in later if s["result"].startswith("BLOCKED")]
            assert all(not s["ok"] for s in blocked)
            # page must not have been submitted (httpbin /post shows JSON with "form")
            st = A.get(f"{BASE_URL}/api/browser/state").json()
            print("tabs", st["tabs"])
            assert not any(t["url"].rstrip("/").endswith("httpbin.org/post") for t in st["tabs"])
        finally:
            if saved:
                A.post(f"{BASE_URL}/api/permissions", json={"category": "send"})
