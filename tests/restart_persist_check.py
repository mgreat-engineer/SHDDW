# Iter7: workspace persistence across backend restart (run: python /app/tests/restart_persist_check.py)
import subprocess
import sys
import time

import requests
from dotenv import dotenv_values

API = dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
tok = subprocess.check_output(["python", "/app/tests/clerk_token.py", "shadow.a+clerk_test@example.com"], text=True).strip()
S = requests.Session()
S.headers["Authorization"] = "Bearer " + tok
res = []


def check(name, cond, info=""):
    res.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name, info)


def groups():
    return {g["id"]: g for g in S.get(f"{API}/browser/groups", timeout=120).json()["groups"]}


mode = sys.argv[1] if len(sys.argv) > 1 else "all"
r1 = S.post(f"{API}/browser/groups", json={"name": "TEST_R1", "label": "TEST Carelon Co", "url": "https://example.com"}, timeout=90).json()
r2 = S.post(f"{API}/browser/groups", json={"name": "TEST_R2", "label": "TEST ICANotes", "url": "https://example.org"}, timeout=90).json()
g1, g2 = r1["id"], r2["id"]
S.post(f"{API}/browser/tabs", params={"group": g1}, json={"action": "new", "url": "https://httpbin.org/cookies/set?restart=r1"}, timeout=60)
S.post(f"{API}/browser/tabs", params={"group": g2}, json={"action": "new", "url": "https://example.net"}, timeout=60)
before = groups()
print("before:", {k: (v["name"], v["label"], v["urls"], v["active"]) for k, v in before.items()})
run = S.post(f"{API}/runs", params={"group": g2}, json={"command": "open example.com, then wait 25 seconds, then tell me the page title"}, timeout=60).json()
rid = run["id"]
time.sleep(13)
print("run before restart:", S.get(f"{API}/runs/{rid}").json()["status"])
t0 = time.time()
subprocess.run(["sudo", "supervisorctl", "restart", "backend"], check=False)
after = None
for _ in range(40):
    try:
        r = S.get(f"{API}/browser/groups", timeout=120)
        if r.status_code == 200:
            after = {g["id"]: g for g in r.json()["groups"]}
            break
    except Exception:
        pass
    time.sleep(3)
print("groups back after %.1fs" % (time.time() - t0))
print("after:", {k: (v["name"], v["label"], v["urls"], v["active"]) for k, v in (after or {}).items()})
check("ids preserved", after and set(before) == set(after), f"{set(before)} vs {set(after or {})}")
for gid in (g1, g2):
    b, a = before[gid], (after or {}).get(gid, {})
    check(f"{gid} name/label", a.get("name") == b["name"] and a.get("label") == b["label"])
    # g2 runs a task that navigates its tab before the restart, so compare tab count there
    same = a.get("urls") == b["urls"] if gid == g1 else len(a.get("urls") or []) == len(b["urls"])
    check(f"{gid} urls", same, f"{b['urls']} -> {a.get('urls')}")
check("main urls", (after or {}).get("1", {}).get("urls") == before["1"]["urls"], f"{before['1']['urls']} -> {(after or {}).get('1', {}).get('urls')}")
rr = S.get(f"{API}/runs/{rid}").json()
check("run paused after restart", rr["status"] == "paused", rr["status"] + " | " + (rr.get("summary") or ""))
check("groups list shows paused run", (after or {}).get(g2, {}).get("run", {}) and after[g2]["run"]["status"] == "paused")
time.sleep(5)
check("still paused (not auto-resumed)", S.get(f"{API}/runs/{rid}").json()["status"] == "paused")
# cookie persisted in R1
S.post(f"{API}/browser/navigate", params={"group": g1}, json={"url": "https://httpbin.org/cookies"}, timeout=60)
time.sleep(1.5)
open("/tmp/restart_r1_cookies.jpg", "wb").write(S.get(f"{API}/browser/frame", params={"group": g1, "quality": 80}).content)
S.post(f"{API}/browser/navigate", params={"group": g2}, json={"url": "https://httpbin.org/cookies"}, timeout=60)
time.sleep(1.5)
open("/tmp/restart_r2_cookies.jpg", "wb").write(S.get(f"{API}/browser/frame", params={"group": g2, "quality": 80}).content)
# resume
rs = S.post(f"{API}/runs/{rid}/resume", timeout=90)
check("resume 200", rs.status_code == 200, rs.text[:200])
end = time.time() + 180
while time.time() < end:
    rr = S.get(f"{API}/runs/{rid}").json()
    if rr["status"] not in ("running",):
        break
    time.sleep(3)
check("resumed run completed", rr["status"] == "completed", rr["status"] + " | " + (rr.get("summary") or ""))
check("same workspace id", rr.get("group_id") == g2)
g_now = groups()
check("workspace not renamed to Resumed:", g_now[g2]["name"] == "TEST_R2" and g_now[g2]["label"] == "TEST ICANotes", g_now[g2]["name"])
check("no extra workspace", set(g_now) == set(before), str(set(g_now) - set(before)))
if mode != "keep":
    for gid in (g1, g2):
        print("close", gid, S.delete(f"{API}/browser/groups/{gid}", timeout=60).status_code)
print("SUMMARY", sum(1 for _, ok in res if ok), "/", len(res))
