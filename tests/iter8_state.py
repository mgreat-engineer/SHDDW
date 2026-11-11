# quick state dump for user A: workspaces + templates (+ optional delete of TEST_ templates by id listed)
import subprocess, requests
from dotenv import dotenv_values
API = dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
tok = subprocess.check_output(["python", "/app/tests/clerk_token.py", "shadow.a+clerk_test@example.com"], text=True).strip()
s = requests.Session(); s.headers["Authorization"] = "Bearer " + tok
for g in s.get(f"{API}/browser/groups", timeout=60).json()["groups"]:
    print("WS", g["id"], g["name"], g["label"], g["urls"], (g.get("run") or {}).get("status"))
for t in s.get(f"{API}/templates").json():
    print("TPL", t["id"], t["name"], t["urls"], t.get("skill_name"))
for sk in s.get(f"{API}/skills").json():
    if sk["name"].startswith("TEST_"):
        print("SKILL", sk["id"], sk["name"])
