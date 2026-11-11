# Agent sign_in probe: runs a task in a TEST_ workspace and checks the sign_in tool is used and /secure reached.
import json
import time

import requests
from dotenv import dotenv_values

API = dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
H = {"Authorization": "Bearer " + open("/tmp/ta.txt").read().strip()}
g = requests.post(f"{API}/browser/groups", json={"name": "TEST_agent_signin", "url": "https://example.com"}, headers=H, timeout=60).json()["id"]
print("group", g)
try:
    r = requests.post(f"{API}/runs?group={g}", json={"command": "Open https://the-internet.herokuapp.com/login, sign in with my saved login and tell me the message shown"}, headers=H, timeout=60)
    print(r.status_code, r.text[:300])
    rid = r.json().get("id") or r.json().get("run", {}).get("id")
    run = {}
    for _ in range(60):
        time.sleep(4)
        run = requests.get(f"{API}/runs/{rid}", headers=H, timeout=60).json()
        if run["status"] not in ("running", "queued", "starting"):
            break
    print("status:", run["status"])
    for s in sorted(run.get("steps", []), key=lambda x: x.get("idx", 0)):
        print(" -", s.get("action"), json.dumps(s.get("args"))[:120], "|", str(s.get("result"))[:160])
    print("final:", json.dumps({k: run.get(k) for k in ("result", "summary", "answer", "question", "final")})[:800])
    st = requests.get(f"{API}/browser/state?group={g}", headers=H, timeout=60).json()
    print("url:", [t["url"] for t in st["tabs"] if t["active"]])
    blob = json.dumps(run)
    print("password leaked in run doc:", "SuperSecretPassword" in blob.replace("SuperSecretPassword! for the password", ""))
finally:
    requests.delete(f"{API}/browser/groups/{g}", headers=H, timeout=60)
