# Iter12: wrong-password offer is hidden on /login, re-appears after navigating away (stale), and expires after ~90s.
import sys, time
sys.path.insert(0, "/app/backend/tests")
import requests
from test_iter12_retest import API, ORIGIN, token

A = requests.Session(); A.headers["Authorization"] = "Bearer " + token()
g = A.post(f"{API}/browser/groups", json={"name": "TEST_expiry", "url": ORIGIN + "/login"}, timeout=60).json()
g = g.get("id") or g["group"]["id"]
try:
    time.sleep(3)
    st = A.get(f"{API}/browser/state?group={g}").json()
    A.post(f"{API}/passwords/{st['saved_logins'][0]['id']}/fill?group={g}")
    A.post(f"{API}/browser/input?group={g}", json={"kind": "type", "text": "WRONG"})
    A.post(f"{API}/browser/input?group={g}", json={"kind": "key", "key": "Enter"})
    t0 = time.time(); time.sleep(3)
    print("on /login offer:", A.get(f"{API}/browser/state?group={g}").json()["save_password"])
    A.post(f"{API}/browser/navigate?group={g}", json={"url": "https://example.com"}, timeout=60)
    time.sleep(1)
    print("after nav away offer:", A.get(f"{API}/browser/state?group={g}").json()["save_password"])
    time.sleep(max(0, 93 - (time.time() - t0)))
    print(f"after {time.time()-t0:.0f}s offer:", A.get(f"{API}/browser/state?group={g}").json()["save_password"])
finally:
    print("delete ws:", A.delete(f"{API}/browser/groups/{g}", timeout=60).status_code)
