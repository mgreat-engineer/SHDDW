import time, urllib.parse, requests
from dotenv import dotenv_values
U = dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"].rstrip("/")
H = {"Authorization": "Bearer " + open("/tmp/ta").read().strip()}
html = "data:text/html," + urllib.parse.quote("<title>Start</title><button style='width:400px;height:200px' onclick=\"document.title=confirm('Proceed with test?')?'ACCEPTED':'DISMISSED'\">Go</button>")
print(requests.post(U + "/api/browser/navigate", json={"url": html}, headers=H).status_code)
r = requests.post(U + "/api/runs", json={"command": "On the current page, click the Go button, accept the confirmation dialog that appears, then tell me the page title. Do not navigate anywhere else."}, headers=H).json()
rid = r["id"]; print("run", rid)
end = time.time() + 150
while time.time() < end:
    run = requests.get(U + f"/api/runs/{rid}", headers=H).json()
    if run["status"] not in ("running",):
        break
    time.sleep(4)
print("status:", run["status"], "| summary:", run.get("summary"), "| pending:", run.get("pending"))
for s in reversed(run["steps"]):
    print(s["idx"], s["action"], s["args"], s["ok"], s["result"][:150])
if run["status"] in ("running", "paused", "awaiting_approval", "waiting_input"):
    print("stop:", requests.post(U + f"/api/runs/{rid}/stop", headers=H).status_code)
print("state dialog:", requests.get(U + "/api/browser/state", headers=H).json()["dialog"])
