# Iter14: new-username login on a different demo site -> 'Save password?' (update False). Usage: python iter14_pw_new.py [shot|run X1 Y1 X2 Y2]
import sys, time
sys.path.insert(0, "/app/backend/tests")
import requests
from test_iter12_retest import API, token

A = requests.Session(); A.headers["Authorization"] = "Bearer " + token()
P = "https://practicetestautomation.com/practice-test-login/"
g = A.post(f"{API}/browser/groups", json={"name": "TEST_iter14_new", "url": P}, timeout=60).json()
g = g.get("id") or g["group"]["id"]
try:
    time.sleep(5)
    if sys.argv[1] == "shot":
        open("/tmp/ptl.jpg", "wb").write(A.get(f"{API}/browser/frame?group={g}").content)
    else:
        x1, y1, x2, y2 = map(int, sys.argv[2:6])
        A.post(f"{API}/browser/input?group={g}", json={"kind": "click", "x": x1, "y": y1})
        A.post(f"{API}/browser/input?group={g}", json={"kind": "type", "text": "student"})
        A.post(f"{API}/browser/input?group={g}", json={"kind": "click", "x": x2, "y": y2})
        A.post(f"{API}/browser/input?group={g}", json={"kind": "type", "text": "Password123"})
        A.post(f"{API}/browser/input?group={g}", json={"kind": "click", "x": 403, "y": 755})
        time.sleep(5)
        st = A.get(f"{API}/browser/state?group={g}").json()
        print("url:", [t for t in st["tabs"] if t["active"]][0]["url"], "offer:", st["save_password"])
        open("/tmp/ptl2.jpg", "wb").write(A.get(f"{API}/browser/frame?group={g}").content)
        off = st["save_password"]
        print("RESULT", "PASS" if off and off["update"] is False and off["username"] == "student" else "FAIL")
        print("dismiss:", A.post(f"{API}/passwords/offer?group={g}", json={"action": "dismiss"}).json())
finally:
    print("delete ws:", A.delete(f"{API}/browser/groups/{g}", timeout=60).status_code)
