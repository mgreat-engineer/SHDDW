# Shadow iteration-14: password CSV import, bookmark folders API, Chrome bookmarks import via simulated helper
# Run: pytest /app/backend/tests/test_iter14_folders_import.py -n 0 -v -s
import asyncio
import json
import subprocess
import threading
import time

import pytest
import requests
import websockets
from dotenv import dotenv_values

BASE_URL = dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"].rstrip("/")
WS_URL = BASE_URL.replace("https://", "wss://") + "/api/helper/ws"
A_EMAIL = "shadow.a+clerk_test@example.com"
TEST_ORIGIN = "https://test-iter14-import.example.com"


@pytest.fixture(scope="module")
def A():
    s = requests.Session()
    s.headers["Authorization"] = "Bearer " + subprocess.check_output(["python", "/app/tests/clerk_token.py", A_EMAIL], text=True).strip()
    return s


def upload(s, content: bytes, name="p.csv"):
    return s.post(f"{BASE_URL}/api/passwords/import", files={"file": (name, content, "text/csv")})


# ---------- Passwords CSV import ----------
class TestPasswordImport:
    def test_import_valid_and_skips(self, A):
        csv = ("name,url,username,password,note\n"
               f"t1,{TEST_ORIGIN}/login,TEST_u1,Pw1,\n"
               f"t2,{TEST_ORIGIN}/x,TEST_u2,Pw2,n\n"
               "t3,,TEST_u3,Pw3,\n"
               f"t4,{TEST_ORIGIN}/,TEST_u4,,\n").encode()
        r = upload(A, csv)
        assert r.status_code == 200, r.text
        assert r.json() == {"saved": 2, "skipped": 2}
        lst = A.get(f"{BASE_URL}/api/passwords").json()
        mine = [p for p in lst if p["origin"] == TEST_ORIGIN]
        assert sorted(p["username"] for p in mine) == ["TEST_u1", "TEST_u2"]
        for p in lst:
            assert "password" not in p and "password_enc" not in p and "pw_mac" not in p
        for p in mine:
            assert A.delete(f"{BASE_URL}/api/passwords/{p['id']}").status_code == 200

    def test_import_bom_and_case(self, A):
        csv = ("\ufeffName,URL,Username,Password\n" f"x,{TEST_ORIGIN},TEST_bom,Pw\n").encode("utf-8")
        r = upload(A, csv)
        assert r.status_code == 200 and r.json()["saved"] == 1, r.text
        for p in A.get(f"{BASE_URL}/api/passwords").json():
            if p["origin"] == TEST_ORIGIN:
                A.delete(f"{BASE_URL}/api/passwords/{p['id']}")

    def test_missing_columns_400(self, A):
        r = upload(A, b"foo,bar\n1,2\n")
        assert r.status_code == 400
        assert "url/password" in r.json()["detail"]

    def test_binary_400(self, A):
        r = upload(A, b"\xff\xfe\x00\x81\x92binary", name="x.png")
        assert r.status_code == 400, r.text

    def test_plain_text_400(self, A):
        r = upload(A, b"hello world this is not csv\n", name="x.txt")
        print("plain text ->", r.status_code, r.text[:150])
        assert r.status_code == 400

    def test_too_large_413(self, A):
        r = upload(A, b"name,url,username,password\n" + b"a" * 5_100_000)
        assert r.status_code == 413

    def test_no_auth_401(self):
        r = requests.post(f"{BASE_URL}/api/passwords/import", files={"file": ("p.csv", b"url,password\n", "text/csv")})
        assert r.status_code in (401, 403)


# ---------- Bookmark folders API ----------
class TestBookmarkFolders:
    def test_folder_crud(self, A):
        ids = []
        try:
            r = A.post(f"{BASE_URL}/api/bookmarks", json={"url": "https://example.com/TEST_iter14a", "title": "TEST_a", "folder": "  TEST_Work   Stuff  "})
            assert r.status_code == 200, r.text
            a = r.json(); ids.append(a["id"])
            assert a["folder"] == "TEST_Work Stuff"
            r = A.post(f"{BASE_URL}/api/bookmarks", json={"url": "https://example.com/TEST_iter14b", "title": "TEST_b", "folder": "TEST_" + "x" * 100})
            b = r.json(); ids.append(b["id"])
            assert len(b["folder"]) == 60
            # edit
            r = A.put(f"{BASE_URL}/api/bookmarks/{b['id']}", json={"title": "TEST_b2", "folder": "TEST_Work Stuff"})
            assert r.status_code == 200 and r.json()["title"] == "TEST_b2" and r.json()["folder"] == "TEST_Work Stuff"
            # blank title ignored
            r = A.put(f"{BASE_URL}/api/bookmarks/{b['id']}", json={"title": "  "})
            assert r.json()["title"] == "TEST_b2"
            # rename
            r = A.post(f"{BASE_URL}/api/bookmarks/folders/rename", json={"old": "TEST_Work Stuff", "new": " TEST_Renamed "})
            assert r.status_code == 200 and r.json()["moved"] == 2
            lst = {x["id"]: x for x in A.get(f"{BASE_URL}/api/bookmarks").json()}
            assert lst[a["id"]]["folder"] == lst[b["id"]]["folder"] == "TEST_Renamed"
            # rename to "" -> bar
            r = A.post(f"{BASE_URL}/api/bookmarks/folders/rename", json={"old": "TEST_Renamed", "new": ""})
            assert r.json()["moved"] == 2
            # 404 on unknown
            assert A.put(f"{BASE_URL}/api/bookmarks/nope-id", json={"title": "x"}).status_code == 404
            # dup url keeps original
            r = A.post(f"{BASE_URL}/api/bookmarks", json={"url": "https://example.com/TEST_iter14a", "title": "other", "folder": "Z"})
            assert r.json()["id"] == a["id"]
            # non http
            assert A.post(f"{BASE_URL}/api/bookmarks", json={"url": "javascript:alert(1)"}).status_code == 400
        finally:
            for i in ids:
                A.delete(f"{BASE_URL}/api/bookmarks/{i}")


# ---------- Chrome bookmarks import through a simulated helper ----------
def run_fake_helper(token, answer, ready, stop):
    async def main():
        async with websockets.connect(WS_URL, additional_headers={"Authorization": "Bearer " + token}, open_timeout=20) as ws:
            await ws.send(json.dumps({"event": "hello", "info": {"version": "TEST"}}))
            ready.set()
            while not stop.is_set():
                try:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), 0.5))
                except asyncio.TimeoutError:
                    continue
                if "method" in msg:
                    await ws.send(json.dumps({"id": msg["id"], **answer(msg["method"])}))
    asyncio.run(main())


class TestImportChrome:
    def test_no_helper_409(self, A):
        r = A.post(f"{BASE_URL}/api/bookmarks/import-chrome")
        assert r.status_code == 409
        assert r.json()["detail"].startswith("Open Shadow Helper")

    @pytest.mark.parametrize("mode", ["new", "old"])
    def test_with_fake_helper(self, A, mode):
        target_before = A.get(f"{BASE_URL}/api/target").json()["target"]
        code = A.post(f"{BASE_URL}/api/devices/pair-code").json()["code"]
        p = requests.post(f"{BASE_URL}/api/helper/pair", json={"code": code, "name": "TEST_iter14_fake"}).json()
        items = [{"title": "TEST_c1", "url": "https://example.com/TEST_chrome1", "folder": "TEST_Chrome / Sub"},
                 {"title": "TEST_c2", "url": "https://example.com/TEST_chrome2", "folder": ""},
                 {"title": "TEST_c1dup", "url": "https://example.com/TEST_chrome1", "folder": "Other"},
                 {"title": "bad", "url": "ftp://x", "folder": ""}]

        def answer(method):
            if method == "chrome_bookmarks":
                return {"result": items} if mode == "new" else {"error": "Not allowed: chrome_bookmarks"}
            return {"error": "TEST fake helper"}
        ready, stop = threading.Event(), threading.Event()
        th = threading.Thread(target=run_fake_helper, args=(p["token"], answer, ready, stop), daemon=True)
        th.start()
        try:
            assert ready.wait(25)
            time.sleep(1.5)
            r = A.post(f"{BASE_URL}/api/bookmarks/import-chrome")
            print(mode, r.status_code, r.text[:200])
            if mode == "new":
                assert r.status_code == 200, r.text
                assert r.json() == {"found": 4, "added": 2}
                lst = {x["url"]: x for x in A.get(f"{BASE_URL}/api/bookmarks").json()}
                assert lst["https://example.com/TEST_chrome1"]["folder"] == "TEST_Chrome / Sub"
                assert lst["https://example.com/TEST_chrome2"]["folder"] == ""
                r2 = A.post(f"{BASE_URL}/api/bookmarks/import-chrome")
                assert r2.json() == {"found": 4, "added": 0}
            else:
                assert r.status_code == 409
                assert r.json()["detail"].startswith("Update Shadow Helper")
        finally:
            stop.set()
            th.join(10)
            A.delete(f"{BASE_URL}/api/devices/{p['device_id']}")
            for b in A.get(f"{BASE_URL}/api/bookmarks").json():
                if "TEST_chrome" in b["url"]:
                    A.delete(f"{BASE_URL}/api/bookmarks/{b['id']}")
        time.sleep(1)
        t = A.get(f"{BASE_URL}/api/target").json()
        print("target before", target_before, "after", t)
        assert t["target"] == "cloud"
