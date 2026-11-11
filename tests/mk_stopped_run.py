# Helper: create a stopped run in a given group (for UI resume-from-history test). usage: python mk_stopped_run.py <gid>
import subprocess, time, requests
from dotenv import dotenv_values
API = dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
s = requests.Session()
s.headers["Authorization"] = "Bearer " + subprocess.check_output(["python", "/app/tests/clerk_token.py", "shadow.a+clerk_test@example.com"], text=True).strip()
g = s.post(f"{API}/browser/groups", json={"name": "TEST_resumeUI", "url": "about:blank"}).json()["id"]; print("group", g)
r = s.post(f"{API}/runs", params={"group": g}, json={"command": "open example.org and tell me the heading"})
print(r.status_code, r.text[:200]); rid = r.json()["id"]
print(s.post(f"{API}/runs/{rid}/stop").status_code)
time.sleep(1)
print(rid, s.get(f"{API}/runs/{rid}").json()["status"])
