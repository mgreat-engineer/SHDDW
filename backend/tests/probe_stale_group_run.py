# Probe: a paused run left in a group id that no longer exists (e.g. after backend restart) gets attached to a new group that reuses that id
import subprocess, uuid, requests
from dotenv import dotenv_values
from pymongo import MongoClient

BASE = dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
_BE = dotenv_values("/app/backend/.env")
DB = MongoClient(_BE["MONGO_URL"])[_BE["DB_NAME"]]
s = requests.Session()
s.headers["Authorization"] = "Bearer " + subprocess.check_output(["python", "/app/tests/clerk_token.py", "shadow.a+clerk_test@example.com"], text=True).strip()
groups = s.get(f"{BASE}/browser/groups").json()["groups"]
print("groups now:", [(g["id"], g["name"]) for g in groups])
uid = DB.runs.find_one({"goal": "open example.com and tell me the page title"}, sort=[("created_at", -1)])["user_id"]
# create+close one group to learn the next id
g = s.post(f"{BASE}/browser/groups", json={"name": "TEST_probe", "url": "about:blank"}).json()
s.delete(f"{BASE}/browser/groups/{g['id']}")
nxt = str(int(g["id"]) + 1)
rid = "TEST_" + str(uuid.uuid4())
DB.runs.insert_one({"id": rid, "user_id": uid, "goal": "TEST_stale paused run", "status": "paused", "group_id": nxt,
                    "created_at": "2026-11-11T00:00:00+00:00", "updated_at": "2026-11-11T00:00:00+00:00", "target": "cloud",
                    "plan": [], "messages": [], "step_count": 0, "mode": "real"})
try:
    g2 = s.post(f"{BASE}/browser/groups", json={"name": "TEST_fresh", "url": "about:blank"}).json()
    print("new group id", g2["id"], "stale run group", nxt)
    info = next(x for x in s.get(f"{BASE}/browser/groups").json()["groups"] if x["id"] == g2["id"])
    print("fresh group run field:", info["run"])
    r = s.post(f"{BASE}/runs", params={"group": g2["id"]}, json={"command": "open example.com"})
    print("start run in fresh group:", r.status_code, r.text[:150])
    if r.status_code == 200:
        s.post(f"{BASE}/runs/{r.json()['id']}/stop")
    print("close fresh group:", s.delete(f"{BASE}/browser/groups/{g2['id']}").status_code)
finally:
    DB.runs.delete_one({"id": rid})
    s.delete(f"{BASE}/browser/groups/{g2['id']}")
    print("cleanup done; groups:", [(g["id"], g["name"]) for g in s.get(f"{BASE}/browser/groups").json()["groups"]])
