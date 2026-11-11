# Iter14: "Update password?" flow on the cloud browser (TEST workspace), same-password no offer, new username -> Save.
import sys, time
sys.path.insert(0, "/app/backend/tests")
import requests
from test_iter12_retest import API, ORIGIN, token

A = requests.Session(); A.headers["Authorization"] = "Bearer " + token()
REAL = "SuperSecretPassword!"


def imp(pw):
    r = A.post(f"{API}/passwords/import", files={"file": ("p.csv", f"name,url,username,password,note\nx,{ORIGIN}/login,tomsmith,{pw},\n".encode(), "text/csv")})
    print("import", pw, r.status_code, r.json())


def tom():
    return [p for p in A.get(f"{API}/passwords").json() if p["origin"] == ORIGIN and p["username"] == "tomsmith"]


def login(g, pw):
    A.post(f"{API}/browser/navigate?group={g}", json={"url": ORIGIN + "/login"}, timeout=60)
    time.sleep(2)
    st = A.get(f"{API}/browser/state?group={g}").json()
    lid = [l for l in st["saved_logins"] if l["username"] == "tomsmith"][0]["id"]
    print(" fill:", A.post(f"{API}/passwords/{lid}/fill?group={g}").status_code)
    if pw:
        A.post(f"{API}/browser/input?group={g}", json={"kind": "key", "key": "Control+a"})
        A.post(f"{API}/browser/input?group={g}", json={"kind": "type", "text": pw})
    A.post(f"{API}/browser/input?group={g}", json={"kind": "key", "key": "Enter"})
    time.sleep(3)
    st = A.get(f"{API}/browser/state?group={g}").json()
    url = [t for t in st["tabs"] if t["active"]][0]["url"]
    print(" url:", url, "offer:", st["save_password"])
    return url, st["save_password"]


before = tom()
print("before:", before)
g = A.post(f"{API}/browser/groups", json={"name": "TEST_iter14_pw", "url": ORIGIN + "/login"}, timeout=60).json()
g = g.get("id") or g["group"]["id"]
try:
    time.sleep(3)
    imp("OldPass1")
    print("1) fill with old saved -> should fail login, no offer")
    url, off = login(g, None)
    print("   RESULT", "PASS" if "/secure" not in url and not off else "FAIL")
    print("2) manual real password -> Update offer")
    url, off = login(g, REAL)
    print("   RESULT", "PASS" if "/secure" in url and off and off["update"] is True and off["username"] == "tomsmith" else "FAIL")
    r = A.post(f"{API}/passwords/offer?group={g}", json={"action": "save"}).json()
    print("   offer save ->", r, "count tomsmith:", len(tom()))
    time.sleep(1)
    print("   offer after save:", A.get(f"{API}/browser/state?group={g}").json()["save_password"])
    A.post(f"{API}/browser/navigate?group={g}", json={"url": ORIGIN + "/logout"}, timeout=60)
    print("3) key fill now logs in, no re-offer")
    url, off = login(g, None)
    print("   RESULT", "PASS" if "/secure" in url and not off else "FAIL")
    A.post(f"{API}/browser/navigate?group={g}", json={"url": ORIGIN + "/logout"}, timeout=60)
    print("4) same password typed manually -> no offer")
    url, off = login(g, REAL)
    print("   RESULT", "PASS" if "/secure" in url and not off else "FAIL")
    print("5) new username (practicetestautomation student) -> Save offer")
    P = "https://practicetestautomation.com/practice-test-login/"
    A.post(f"{API}/browser/navigate?group={g}", json={"url": P}, timeout=60)
    time.sleep(3)
    st = A.get(f"{API}/browser/state?group={g}").json()
    print("   has_password_field", st.get("has_password_field"))
    A.post(f"{API}/browser/input?group={g}", json={"kind": "key", "key": "Tab"})
    # focus username directly via JS-free approach: click on field is unknown; use Tab cycle fallback
finally:
    print("final tomsmith:", tom())
    print("delete ws:", A.delete(f"{API}/browser/groups/{g}", timeout=60).status_code)
