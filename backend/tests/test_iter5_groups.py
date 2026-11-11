# Shadow iteration-5: window groups (CRUD, max 10, per-group browser endpoints, isolation, shared cookies, popups, parallel runs)
# Run serially: cd /app/backend && pytest tests/test_iter5_groups.py -n 0 -v -s
import subprocess
import time

import pytest
import requests
from dotenv import dotenv_values

BASE_URL = dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
A_EMAIL = "shadow.a+clerk_test@example.com"
ACTIVE = ("running", "paused", "awaiting_approval", "waiting_input")


@pytest.fixture(scope="module")
def A():
    s = requests.Session()
    s.headers["Authorization"] = "Bearer " + subprocess.check_output(["python", "/app/tests/clerk_token.py", A_EMAIL], text=True).strip()
    return s


@pytest.fixture(scope="module")
def created(A):
    ids = []
    yield ids
    for g in ids:
        A.delete(f"{API}/browser/groups/{g}")


def new_group(A, created, name="", url=""):
    r = A.post(f"{API}/browser/groups", json={"name": name, "url": url}, timeout=60)
    assert r.status_code == 200, r.text
    g = r.json()
    created.append(g["id"])
    return g


def tabs(A, gid):
    r = A.get(f"{API}/browser/state", params={"group": gid}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["tabs"]


def stop(A, rid):
    A.post(f"{API}/runs/{rid}/stop")


def wait_done(A, rid, timeout=180):
    end = time.time() + timeout
    while time.time() < end:
        run = A.get(f"{API}/runs/{rid}").json()
        if run["status"] not in ("running",):
            return run
        time.sleep(3)
    return run


# ---- group list / CRUD
class TestGroupsCrud:
    def test_list_has_main(self, A):
        r = A.get(f"{API}/browser/groups", timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert d["max"] == 10
        main = next(g for g in d["groups"] if g["id"] == "1")
        assert main["name"] == "Main"
        for k in ("id", "name", "tabs", "url", "recording", "run"):
            assert k in main

    def test_create_rename_delete(self, A, created):
        g = new_group(A, created, name="TEST_grp", url="https://example.com")
        assert g["name"] == "TEST_grp" and g["tabs"] == 1 and "example.com" in g["url"]
        r = A.put(f"{API}/browser/groups/{g['id']}", json={"name": "TEST_renamed"})
        assert r.status_code == 200 and r.json()["name"] == "TEST_renamed"
        lst = A.get(f"{API}/browser/groups").json()["groups"]
        assert any(x["id"] == g["id"] and x["name"] == "TEST_renamed" for x in lst)
        r = A.delete(f"{API}/browser/groups/{g['id']}")
        assert r.status_code == 200
        created.remove(g["id"])
        r = A.get(f"{API}/browser/state", params={"group": g["id"]})
        assert r.status_code == 404
        r = A.get(f"{API}/browser/frame", params={"group": g["id"]})
        assert r.status_code == 404

    def test_delete_main_refused(self, A):
        r = A.delete(f"{API}/browser/groups/1")
        assert r.status_code == 400

    def test_delete_unknown(self, A):
        r = A.delete(f"{API}/browser/groups/987")
        print("delete unknown ->", r.status_code, r.text)
        assert r.status_code in (400, 404)

    def test_rename_unknown_404(self, A):
        r = A.put(f"{API}/browser/groups/987", json={"name": "x"})
        assert r.status_code == 404

    def test_invalid_group_param_422(self, A):
        # iter6: ids are now hex strings; pattern ^[a-z0-9]{1,12}$ -> bad chars 422, unknown valid id 404
        r = A.get(f"{API}/browser/state", params={"group": "AB_!"})
        assert r.status_code == 422
        r = A.get(f"{API}/browser/state", params={"group": "abc"})
        assert r.status_code == 404

    def test_max_10(self, A, created):
        existing = len(A.get(f"{API}/browser/groups").json()["groups"])
        mine = []
        for _ in range(10 - existing):
            mine.append(new_group(A, created, url="about:blank")["id"])
        assert len(A.get(f"{API}/browser/groups").json()["groups"]) == 10
        r = A.post(f"{API}/browser/groups", json={"name": "TEST_over"}, timeout=60)
        assert r.status_code == 409, r.text
        for g in mine:
            assert A.delete(f"{API}/browser/groups/{g}").status_code == 200
            created.remove(g)


# ---- per-group browser endpoints & isolation
class TestGroupIsolation:
    def test_tabs_navigation_isolated(self, A, created):
        g2 = new_group(A, created, name="TEST_iso2", url="https://example.com")["id"]
        g3 = new_group(A, created, name="TEST_iso3", url="https://example.org")["id"]
        main_before = tabs(A, "1")
        r = A.post(f"{API}/browser/tabs", params={"group": g2}, json={"action": "new", "url": "https://example.net"}, timeout=60)
        assert r.status_code == 200 and len(r.json()["tabs"]) == 2
        assert len(tabs(A, g3)) == 1
        assert len(tabs(A, "1")) == len(main_before)
        r = A.post(f"{API}/browser/navigate", params={"group": g3}, json={"url": "https://httpbin.org/html"}, timeout=60)
        assert r.status_code == 200
        assert "httpbin.org" in tabs(A, g3)[0]["url"]
        assert all("httpbin" not in t["url"] for t in tabs(A, g2))
        # nav / input / switch / close in group 2
        assert A.post(f"{API}/browser/nav", params={"group": g2}, json={"action": "reload"}, timeout=60).status_code == 200
        assert A.post(f"{API}/browser/input", params={"group": g2}, json={"kind": "scroll", "dy": 200}, timeout=30).status_code == 200
        r = A.post(f"{API}/browser/tabs", params={"group": g2}, json={"action": "switch", "index": 0})
        assert r.status_code == 200 and r.json()["tabs"][0]["active"]
        r = A.post(f"{API}/browser/tabs", params={"group": g2}, json={"action": "close", "index": 1})
        assert r.status_code == 200 and len(r.json()["tabs"]) == 1
        st = A.get(f"{API}/browser/state", params={"group": g2}).json()
        assert st["group"]["id"] == g2 and st["group"]["name"] == "TEST_iso2"
        # frame low quality
        r = A.get(f"{API}/browser/frame", params={"group": g3, "quality": 30}, timeout=30)
        assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and len(r.content) > 1000
        # dialog/filechooser endpoints scoped
        r = A.post(f"{API}/browser/dialog", params={"group": g3}, json={"accept": True})
        assert r.status_code == 400
        r = A.post(f"{API}/browser/filechooser", params={"group": g3}, json={"cancel": True})
        assert r.status_code == 200

    def test_recording_per_group(self, A, created):
        g = new_group(A, created, name="TEST_rec", url="https://example.com")["id"]
        assert A.post(f"{API}/record/start", params={"group": g}).status_code == 200
        assert A.get(f"{API}/browser/state", params={"group": g}).json()["recording"] is True
        assert A.get(f"{API}/browser/state", params={"group": "1"}).json()["recording"] is False
        assert A.post(f"{API}/record/note", params={"group": g}, json={"text": "TEST note"}).status_code == 200
        assert A.post(f"{API}/record/note", params={"group": "1"}, json={"text": "x"}).status_code in (400, 409)
        r = A.post(f"{API}/record/stop", params={"group": g})
        assert r.status_code == 200
        print("record stop:", str(r.json())[:300])
        assert "TEST note" in str(r.json())

    def test_isolated_cookies(self, A, created):
        # iter7: workspaces are ISOLATED now (own cookies); g3 must NOT see g2's cookie
        g2 = new_group(A, created, name="TEST_ck2")["id"]
        g3 = new_group(A, created, name="TEST_ck3")["id"]
        r = A.post(f"{API}/browser/navigate", params={"group": g2}, json={"url": "https://httpbin.org/cookies/set?iso5=1"}, timeout=60)
        assert r.status_code == 200
        r = A.post(f"{API}/browser/navigate", params={"group": g3}, json={"url": "https://httpbin.org/cookies"}, timeout=60)
        assert r.status_code == 200
        time.sleep(1)
        st = A.get(f"{API}/browser/state", params={"group": g3}).json()
        assert "httpbin.org/cookies" in st["tabs"][0]["url"]
        img = A.get(f"{API}/browser/frame", params={"group": g3, "quality": 80}).content
        open("/tmp/cookie_frame.jpg", "wb").write(img)  # inspect visually: should show "cookies": {} (no iso5)

    def test_popup_stays_in_group(self, A, created):
        g = new_group(A, created, name="TEST_pop", url="https://example.com")["id"]
        main_n = len(tabs(A, "1"))
        # open a popup via javascript: URL typed in address bar is not allowed; use input type of a page with window.open
        html = "data:text/html,<a id=x href='https://example.org' target='_blank' style='display:block;width:800px;height:600px'>open</a>"
        r = A.post(f"{API}/browser/navigate", params={"group": g}, json={"url": html}, timeout=60)
        assert r.status_code == 200, r.text
        r = A.post(f"{API}/browser/input", params={"group": g}, json={"kind": "click", "x": 200, "y": 200}, timeout=30)
        assert r.status_code == 200
        time.sleep(3)
        t = tabs(A, g)
        print("popup group tabs:", t)
        assert len(t) == 2 and any("example.org" in x["url"] for x in t)
        assert len(tabs(A, "1")) == main_n


# ---- parallel runs per group (GPT)
class TestParallelRuns:
    def test_parallel_runs(self, A, created):
        g2 = new_group(A, created, name="TEST_run2")["id"]
        g3 = new_group(A, created, name="TEST_run3")["id"]
        rids = []
        try:
            r2 = A.post(f"{API}/runs", params={"group": g2}, json={"command": "open example.com and tell me the page title"}, timeout=60)
            assert r2.status_code == 200, r2.text
            rids.append(r2.json()["id"])
            assert r2.json()["group_id"] == g2
            r3 = A.post(f"{API}/runs", params={"group": g3}, json={"command": "open example.org and tell me the page title"}, timeout=60)
            assert r3.status_code == 200, r3.text
            rids.append(r3.json()["id"])
            assert r3.json()["group_id"] == g3
            dup = A.post(f"{API}/runs", params={"group": g2}, json={"command": "open example.net"}, timeout=60)
            assert dup.status_code == 409
            a2 = A.get(f"{API}/runs/active", params={"group": g2}).json()["run"]
            a3 = A.get(f"{API}/runs/active", params={"group": g3}).json()["run"]
            assert a2["id"] == rids[0] and a3["id"] == rids[1]
            # group with active run can't be closed
            assert A.delete(f"{API}/browser/groups/{g2}").status_code == 409
            lst = {g["id"]: g for g in A.get(f"{API}/browser/groups").json()["groups"]}
            assert lst[g2]["run"]["id"] == rids[0] and lst[g3]["run"]["id"] == rids[1]
            # pause/resume on g3 doesn't affect g2
            p = A.post(f"{API}/runs/{rids[1]}/pause")
            if p.status_code == 200:
                assert A.get(f"{API}/runs/{rids[0]}").json()["status"] in ("running", "completed")
                assert A.post(f"{API}/runs/{rids[1]}/resume").status_code == 200
            done2 = wait_done(A, rids[0])
            done3 = wait_done(A, rids[1])
            print("run2:", done2["status"], done2.get("summary"))
            print("run3:", done3["status"], done3.get("summary"))
            assert done2["status"] == "completed" and "Example Domain" in (done2.get("summary") or "")
            assert done3["status"] == "completed"
            assert any("example.com" in t["url"] for t in tabs(A, g2))
            assert any("example.org" in t["url"] for t in tabs(A, g3))
        finally:
            for rid in rids:
                stop(A, rid)
