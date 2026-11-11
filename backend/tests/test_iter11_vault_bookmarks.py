# Shadow iteration-11: bookmarks API, saved-password vault API (encrypted, never leaked), selection copy,
# stealth UA (no HeadlessChrome), Google /sorry/ -> Bing fallback. Uses a dedicated TEST_ workspace.
# Run: cd /app/backend && pytest tests/test_iter11_vault_bookmarks.py -n 0 -v -s
import asyncio
import base64
import json
import os
import subprocess
import time

import pytest
import requests
from dotenv import dotenv_values, load_dotenv

BASE_URL = dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
A_EMAIL = "shadow.a+clerk_test@example.com"
B_EMAIL = "shadow.b+clerk_test@example.com"
ORIGIN = "https://the-internet.herokuapp.com"


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
def ws(A):
    r = A.post(f"{API}/browser/groups", json={"name": "TEST_vault", "url": "https://example.com"}, timeout=60)
    assert r.status_code == 200, r.text
    g = r.json().get("id") or r.json().get("group", {}).get("id")
    yield g
    A.delete(f"{API}/browser/groups/{g}", timeout=60)


def state(A, g):
    r = A.get(f"{API}/browser/state?group={g}", timeout=60)
    assert r.status_code == 200, r.text
    return r.json()


def active_url(st):
    return next(t["url"] for t in st["tabs"] if t["active"])


# ---------- bookmarks ----------
class TestBookmarks:
    def test_crud_dupe_isolation(self, A, B):
        url = "https://example.org/TEST_iter11"
        r = A.post(f"{API}/bookmarks", json={"url": url, "title": "TEST_bm"})
        assert r.status_code == 200, r.text
        b = r.json()
        try:
            assert b["url"] == url and b["title"] == "TEST_bm" and isinstance(b["id"], str) and "user_id" not in b
            r2 = A.post(f"{API}/bookmarks", json={"url": url, "title": "other"})
            assert r2.status_code == 200 and r2.json()["id"] == b["id"]
            lst = A.get(f"{API}/bookmarks").json()
            assert sum(1 for x in lst if x["url"] == url) == 1
            assert all(x["url"] != url for x in B.get(f"{API}/bookmarks").json())
            assert B.delete(f"{API}/bookmarks/{b['id']}").status_code == 404
            assert A.post(f"{API}/bookmarks", json={"url": "javascript:alert(1)"}).status_code == 400
            assert A.post(f"{API}/bookmarks", json={"url": "ftp://x.com"}).status_code == 400
        finally:
            assert A.delete(f"{API}/bookmarks/{b['id']}").status_code == 200
        assert all(x["id"] != b["id"] for x in A.get(f"{API}/bookmarks").json())
        assert A.delete(f"{API}/bookmarks/{b['id']}").status_code == 404

    def test_requires_auth(self):
        assert requests.get(f"{API}/bookmarks").status_code in (401, 403)
        assert requests.get(f"{API}/passwords").status_code in (401, 403)


# ---------- stealth / UA ----------
class TestStealth:
    def test_headers_ua(self, A, ws):
        r = A.post(f"{API}/browser/navigate?group={ws}", json={"url": "https://httpbin.org/headers"}, timeout=60)
        assert r.status_code == 200, r.text
        time.sleep(1.5)
        A.post(f"{API}/browser/input?group={ws}", json={"kind": "key", "key": "Control+a"})
        time.sleep(0.5)
        txt = A.get(f"{API}/browser/selection?group={ws}").json()["text"]
        print(txt[:1200])
        ua = [l for l in txt.splitlines() if '"User-Agent"' in l]
        assert ua and "Chrome/" in ua[0] and "HeadlessChrome" not in ua[0]
        chua = [l for l in txt.splitlines() if '"Sec-Ch-Ua"' in l]
        assert chua and "Google Chrome" in chua[0]

    def test_google_search_not_stuck(self, A, ws):
        r = A.post(f"{API}/browser/navigate?group={ws}", json={"url": "best grant programs 2026"}, timeout=90)
        assert r.status_code == 200, r.text
        final = ""
        for _ in range(12):
            time.sleep(1.5)
            final = active_url(state(A, ws))
            if "/sorry/" not in final and ("bing.com/search" in final or "google.com/search" in final):
                break
        print("search final url:", final)
        assert "/sorry/" not in final
        assert "bing.com/search" in final or "google.com/search" in final


# ---------- passwords ----------
class TestPasswords:
    def test_list_has_no_secret(self, A, B):
        lst = A.get(f"{API}/passwords").json()
        assert any(p["origin"] == ORIGIN and p["username"] == "tomsmith" for p in lst)
        for p in lst:
            assert set(p) <= {"id", "origin", "username", "updated_at"}
        assert all(p["origin"] != ORIGIN for p in B.get(f"{API}/passwords").json())

    def test_encrypted_at_rest(self, A):
        load_dotenv("/app/backend/.env")
        from motor.motor_asyncio import AsyncIOMotorClient
        uid = json.loads(base64.urlsafe_b64decode(A.headers["Authorization"].split()[1].split(".")[1] + "==="))["sub"]

        async def go():
            db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
            return await db.passwords.find_one({"user_id": uid, "origin": ORIGIN, "username": "tomsmith"})
        d = asyncio.run(go())
        assert d and "SuperSecretPassword" not in d["password_enc"] and "password" not in d

    def test_fill_wrong_site_400_and_other_user_404(self, A, B, ws):
        pid = next(p["id"] for p in A.get(f"{API}/passwords").json() if p["origin"] == ORIGIN)
        A.post(f"{API}/browser/navigate?group={ws}", json={"url": "https://example.com"}, timeout=60)
        r = A.post(f"{API}/passwords/{pid}/fill?group={ws}")
        assert r.status_code == 400, r.text
        assert B.post(f"{API}/passwords/{pid}/fill").status_code == 404
        assert B.delete(f"{API}/passwords/{pid}").status_code == 404

    def test_fill_login_and_no_reoffer(self, A, ws):
        A.post(f"{API}/browser/navigate?group={ws}", json={"url": ORIGIN + "/login"}, timeout=60)
        time.sleep(1.5)
        st = state(A, ws)
        assert st["has_password_field"] is True
        assert st["saved_logins"] and st["saved_logins"][0]["username"] == "tomsmith"
        assert set(st["saved_logins"][0]) == {"id", "username"}
        raw = json.dumps(st)
        assert "SuperSecret" not in raw and "pw_sha" not in raw
        r = A.post(f"{API}/passwords/{st['saved_logins'][0]['id']}/fill?group={ws}")
        assert r.status_code == 200 and "password" in r.json()["result"], r.text
        A.post(f"{API}/browser/input?group={ws}", json={"kind": "key", "key": "Enter"})
        url = ""
        for _ in range(10):
            time.sleep(1)
            st = state(A, ws)
            url = active_url(st)
            if "/secure" in url:
                break
        assert "/secure" in url, url
        assert st["save_password"] is None  # same saved password -> not re-offered
        raw = json.dumps(st)
        assert "SuperSecret" not in raw and "pw_sha" not in raw
        r = A.post(f"{API}/passwords/offer?group={ws}", json={"action": "save"})
        assert r.status_code == 200 and r.json()["saved"] is False
