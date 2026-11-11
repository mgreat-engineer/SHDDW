# Shadow AI browser - backend regression tests (auth, CRUD, browser, recording, dialogs, files, isolation, runs, approvals)
# Run serially: pytest /app/backend/tests/test_shadow_api.py -n 0 -v
import subprocess
import time
import urllib.parse

import pytest
import requests
from dotenv import dotenv_values

BASE_URL = dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"].rstrip("/")
A_EMAIL = "shadow.a+clerk_test@example.com"
B_EMAIL = "shadow.b+clerk_test@example.com"


def token(email):
    return subprocess.check_output(["python", "/app/tests/clerk_token.py", email], text=True).strip()


@pytest.fixture(scope="module")
def A():
    s = requests.Session()
    s.headers["Authorization"] = "Bearer " + token(A_EMAIL)
    return s


@pytest.fixture(scope="module")
def B():
    s = requests.Session()
    s.headers["Authorization"] = "Bearer " + token(B_EMAIL)
    return s


def stop_active(s):
    r = s.get(f"{BASE_URL}/api/runs/active").json()
    if r.get("run"):
        s.post(f"{BASE_URL}/api/runs/{r['run']['id']}/stop")


def wait_run(s, rid, until, timeout=150):
    end = time.time() + timeout
    run = None
    while time.time() < end:
        run = s.get(f"{BASE_URL}/api/runs/{rid}").json()
        if run["status"] in until:
            return run
        time.sleep(3)
    return run


# ---- Auth ----
class TestAuth:
    @pytest.mark.parametrize("path", ["/api/status", "/api/skills", "/api/runs", "/api/memories", "/api/files", "/api/permissions", "/api/browser/state"])
    def test_unauth_401(self, path):
        assert requests.get(BASE_URL + path).status_code == 401

    def test_status(self, A):
        r = A.get(f"{BASE_URL}/api/status")
        assert r.status_code == 200 and r.json()["openai_configured"] is True


# ---- Memory / skills / permissions CRUD + isolation ----
class TestCrud:
    def test_memory_crud_and_isolation(self, A, B):
        m = A.post(f"{BASE_URL}/api/memories", json={"content": "TEST_ likes tea"}).json()
        assert m["content"] == "TEST_ likes tea"
        assert any(x["id"] == m["id"] for x in A.get(f"{BASE_URL}/api/memories").json())
        assert all(x["id"] != m["id"] for x in B.get(f"{BASE_URL}/api/memories").json())
        assert B.put(f"{BASE_URL}/api/memories/{m['id']}", json={"content": "hack"}).status_code == 404
        assert B.delete(f"{BASE_URL}/api/memories/{m['id']}").status_code == 404
        assert A.put(f"{BASE_URL}/api/memories/{m['id']}", json={"content": "TEST_ likes coffee"}).status_code == 200
        assert any(x["content"] == "TEST_ likes coffee" for x in A.get(f"{BASE_URL}/api/memories").json())
        assert A.post(f"{BASE_URL}/api/memories", json={"content": "  "}).status_code == 400
        assert A.delete(f"{BASE_URL}/api/memories/{m['id']}").status_code == 200
        assert A.delete(f"{BASE_URL}/api/memories/{m['id']}").status_code == 404

    def test_skill_crud_and_isolation(self, A, B):
        sk = A.post(f"{BASE_URL}/api/skills", json={"name": "TEST_skill", "description": "d", "steps": ["a", "b"]}).json()
        assert sk["name"] == "TEST_skill" and "_id" not in sk
        assert all(x["id"] != sk["id"] for x in B.get(f"{BASE_URL}/api/skills").json())
        assert B.put(f"{BASE_URL}/api/skills/{sk['id']}", json={"name": "x"}).status_code == 404
        assert B.post(f"{BASE_URL}/api/runs", json={"skill_id": sk["id"]}).status_code == 404
        up = A.put(f"{BASE_URL}/api/skills/{sk['id']}", json={"name": "TEST_skill2", "steps": ["c"]}).json()
        assert up["name"] == "TEST_skill2" and up["steps"] == ["c"]
        assert B.delete(f"{BASE_URL}/api/skills/{sk['id']}").status_code == 404
        assert A.delete(f"{BASE_URL}/api/skills/{sk['id']}").status_code == 200

    def test_permissions(self, A, B):
        assert A.post(f"{BASE_URL}/api/permissions", json={"category": "bogus"}).status_code == 400
        lst = B.post(f"{BASE_URL}/api/permissions", json={"category": "delete"}).json()
        p = [x for x in lst if x["category"] == "delete"][0]
        assert A.delete(f"{BASE_URL}/api/permissions/{p['id']}").status_code == 404
        assert B.delete(f"{BASE_URL}/api/permissions/{p['id']}").status_code == 200

    def test_files_upload_download_isolation(self, A, B):
        r = A.post(f"{BASE_URL}/api/files", files={"file": ("TEST_up.txt", b"hello shadow")})
        assert r.status_code == 200
        f = r.json()
        assert f["name"] == "TEST_up.txt" and f["size"] == 12
        d = A.get(f"{BASE_URL}/api/files/{f['id']}/download")
        assert d.status_code == 200 and d.content == b"hello shadow"
        assert B.get(f"{BASE_URL}/api/files/{f['id']}/download").status_code == 404
        assert B.delete(f"{BASE_URL}/api/files/{f['id']}").status_code == 404
        assert A.delete(f"{BASE_URL}/api/files/{f['id']}").status_code == 200
        assert A.get(f"{BASE_URL}/api/files/{f['id']}/download").status_code == 404


# ---- Live browser: navigate, tabs, frame, recording, dialogs, file chooser ----
class TestBrowser:
    def test_navigate_and_frame(self, A):
        stop_active(A)
        assert A.post(f"{BASE_URL}/api/browser/navigate", json={"url": "example.com"}).status_code == 200
        st = A.get(f"{BASE_URL}/api/browser/state").json()
        act = [t for t in st["tabs"] if t["active"]][0]
        assert "Example Domain" in act["title"]
        fr = A.get(f"{BASE_URL}/api/browser/frame")
        assert fr.status_code == 200 and fr.headers["content-type"] == "image/jpeg" and len(fr.content) > 1000

    def test_tabs(self, A):
        n0 = len(A.get(f"{BASE_URL}/api/browser/state").json()["tabs"])
        st = A.post(f"{BASE_URL}/api/browser/tabs", json={"action": "new", "url": "https://example.org"}).json()
        assert len(st["tabs"]) == n0 + 1 and st["tabs"][-1]["active"]
        st = A.post(f"{BASE_URL}/api/browser/tabs", json={"action": "switch", "index": 0}).json()
        assert st["tabs"][0]["active"]
        st = A.post(f"{BASE_URL}/api/browser/tabs", json={"action": "close", "index": n0}).json()
        assert len(st["tabs"]) == n0
        assert A.post(f"{BASE_URL}/api/browser/tabs", json={"action": "switch", "index": 99}).status_code == 400

    def test_recording_click(self, A):
        A.post(f"{BASE_URL}/api/browser/navigate", json={"url": "https://example.com"})
        assert A.post(f"{BASE_URL}/api/record/start").status_code == 200
        assert A.get(f"{BASE_URL}/api/browser/state").json()["recording"] is True
        # click "Learn more" link roughly; find via the text location is unknown -> use keyboard Tab+Enter
        A.post(f"{BASE_URL}/api/browser/input", json={"kind": "key", "key": "Tab"})
        A.post(f"{BASE_URL}/api/browser/input", json={"kind": "key", "key": "Enter"})
        time.sleep(3)
        assert A.post(f"{BASE_URL}/api/record/note", json={"text": "TEST note"}).status_code == 200
        ev = A.post(f"{BASE_URL}/api/record/stop").json()["events"]
        descs = [e["desc"] for e in ev]
        print(descs)
        assert any("USER NOTE" in d for d in descs)
        assert any("iana" in d.lower() for d in descs)
        assert A.post(f"{BASE_URL}/api/record/note", json={"text": "x"}).status_code == 400

    def test_confirm_dialog(self, A):
        html = "data:text/html," + urllib.parse.quote("<button id=b style='width:400px;height:200px' onclick=\"document.title=confirm('Sure?')?'YES':'NO'\">Go</button>")
        assert A.post(f"{BASE_URL}/api/browser/navigate", json={"url": html}).status_code == 200
        # NOTE: /browser/input click blocks until the dialog is resolved, so fire it in a thread
        import threading
        th = threading.Thread(target=lambda: A.post(f"{BASE_URL}/api/browser/input", json={"kind": "click", "x": 100, "y": 50}, timeout=60))
        th.start()
        time.sleep(3)
        st = A.get(f"{BASE_URL}/api/browser/state", timeout=30).json()
        assert st["dialog"] and st["dialog"]["type"] == "confirm" and st["dialog"]["message"] == "Sure?"
        fr = A.get(f"{BASE_URL}/api/browser/frame", timeout=30)
        print("frame while dialog", fr.status_code)
        assert A.post(f"{BASE_URL}/api/browser/dialog", json={"accept": True}).status_code == 200
        th.join()
        time.sleep(1)
        st = A.get(f"{BASE_URL}/api/browser/state").json()
        assert st["dialog"] is None
        assert [t for t in st["tabs"] if t["active"]][0]["title"] == "YES"
        assert A.post(f"{BASE_URL}/api/browser/dialog", json={"accept": True}).status_code == 400

    def test_file_chooser(self, A):
        A.post(f"{BASE_URL}/api/files", files={"file": ("TEST_chooser.txt", b"abc")})
        html = "data:text/html," + urllib.parse.quote("<input type=file id=f style='width:400px;height:100px' onchange=\"document.title='GOT:'+this.files[0].name\">")
        A.post(f"{BASE_URL}/api/browser/navigate", json={"url": html})
        A.post(f"{BASE_URL}/api/browser/input", json={"kind": "click", "x": 100, "y": 40})
        time.sleep(1)
        assert A.get(f"{BASE_URL}/api/browser/state").json()["file_chooser"] is True
        assert A.post(f"{BASE_URL}/api/browser/filechooser", json={"file_names": ["nope.txt"]}).status_code == 400
        assert A.post(f"{BASE_URL}/api/browser/filechooser", json={"file_names": ["TEST_chooser.txt"]}).status_code == 200
        time.sleep(1)
        st = A.get(f"{BASE_URL}/api/browser/state").json()
        assert [t for t in st["tabs"] if t["active"]][0]["title"] == "GOT:TEST_chooser.txt"
        f = [x for x in A.get(f"{BASE_URL}/api/files").json() if x["name"] == "TEST_chooser.txt"][0]
        A.delete(f"{BASE_URL}/api/files/{f['id']}")


# ---- Agent runs (GPT) ----
class TestRuns:
    def test_command_run_completes(self, A, B):
        stop_active(A)
        r = A.post(f"{BASE_URL}/api/runs", json={"command": "Go to example.com and tell me the heading text"})
        assert r.status_code == 200
        rid = r.json()["id"]
        assert A.post(f"{BASE_URL}/api/runs", json={"command": "another"}).status_code == 409
        assert B.get(f"{BASE_URL}/api/runs/{rid}").status_code == 404
        assert B.post(f"{BASE_URL}/api/runs/{rid}/stop").status_code == 404
        run = wait_run(A, rid, ("completed", "failed", "stopped", "awaiting_approval", "waiting_input"))
        print(run["status"], run.get("summary"), len(run["steps"]))
        assert run["status"] == "completed"
        assert "example domain" in run["summary"].lower()
        assert run["steps"] and run["steps"][0]["has_shot"]
        assert A.get(f"{BASE_URL}/api/runs/{rid}/shot/{run['steps'][0]['idx']}").status_code == 200
        assert B.get(f"{BASE_URL}/api/runs/{rid}/shot/1").status_code == 404

    def test_approval_reject_then_always(self, A):
        stop_active(A)
        for p in A.get(f"{BASE_URL}/api/permissions").json():
            if p["category"] == "send":
                A.delete(f"{BASE_URL}/api/permissions/{p['id']}")
        r = A.post(f"{BASE_URL}/api/runs", json={"command": "Go to https://httpbin.org/forms/post, fill customer name Test, and submit the order"})
        rid = r.json()["id"]
        run = wait_run(A, rid, ("awaiting_approval", "completed", "failed", "stopped", "waiting_input"), 200)
        print("status", run["status"], run.get("pending"))
        assert run["status"] == "awaiting_approval" and run["pending"]["risk"] == "send"
        assert A.post(f"{BASE_URL}/api/runs/{rid}/approval", json={"decision": "always"}).status_code == 200
        assert any(p["category"] == "send" for p in A.get(f"{BASE_URL}/api/permissions").json())
        run = wait_run(A, rid, ("completed", "failed", "stopped", "awaiting_approval", "waiting_input"), 200)
        print("final", run["status"], run.get("summary"))
        if run["status"] in ("running", "awaiting_approval", "waiting_input", "paused"):
            A.post(f"{BASE_URL}/api/runs/{rid}/stop")
        assert run["status"] == "completed"

    def test_pause_resume_stop(self, A):
        stop_active(A)
        rid = A.post(f"{BASE_URL}/api/runs", json={"command": "Open wikipedia.org, search for Python programming language, and summarize the first paragraph"}).json()["id"]
        time.sleep(4)
        assert A.post(f"{BASE_URL}/api/runs/{rid}/pause").status_code == 200
        assert A.get(f"{BASE_URL}/api/runs/{rid}").json()["status"] == "paused"
        assert A.post(f"{BASE_URL}/api/runs/{rid}/resume").status_code == 200
        assert A.get(f"{BASE_URL}/api/runs/{rid}").json()["status"] == "running"
        assert A.post(f"{BASE_URL}/api/runs/{rid}/stop").status_code == 200
        time.sleep(15)
        run = A.get(f"{BASE_URL}/api/runs/{rid}").json()
        assert run["status"] == "stopped"
        assert any(x["id"] == rid for x in A.get(f"{BASE_URL}/api/runs").json())
