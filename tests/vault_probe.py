import asyncio
import subprocess
import sys
import time

import requests
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv  # noqa: E402

load_dotenv("/app/backend/.env")
import os  # noqa: E402

import shadow_vault as vault  # noqa: E402

API = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0] + "/api"
tok = subprocess.check_output([sys.executable, "/app/tests/clerk_token.py", "shadow.a+clerk_test@example.com"]).decode().strip()
H = {"Authorization": f"Bearer {tok}"}
get = lambda p: requests.get(API + p, headers=H, timeout=60).json()  # noqa: E731
post = lambda p, j=None: requests.post(API + p, headers=H, json=j or {}, timeout=60).json()  # noqa: E731

print(post("/browser/navigate", {"url": "https://httpbin.org/headers"}))
time.sleep(1)
post("/browser/input", {"kind": "key", "key": "Control+a"})
sel = get("/browser/selection")["text"]; print("UA:", [l for l in sel.splitlines() if "User-Agent" in l or "Sec-Ch-Ua" in l])

import base64, json; uid = json.loads(base64.urlsafe_b64decode(tok.split(".")[1] + "==="))["sub"]
db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
ORIGIN = "https://the-internet.herokuapp.com"


async def seed(u):
    await vault.save(db, u, ORIGIN, "tomsmith", "SuperSecretPassword!")
    d = await db.passwords.find_one({"user_id": u, "origin": ORIGIN})
    print("stored encrypted:", "SuperSecret" not in d["password_enc"])

asyncio.run(seed(uid))
print(post("/browser/navigate", {"url": ORIGIN + "/login"}))
time.sleep(1.5)
st = get("/browser/state")
print("has_pw", st["has_password_field"], "saved", st["saved_logins"])
pid = st["saved_logins"][0]["id"]
print("fill", post(f"/passwords/{pid}/fill"))
print(post("/browser/input", {"kind": "key", "key": "Enter"}))
time.sleep(2)
st = get("/browser/state")
print("after login url:", [t["url"] for t in st["tabs"] if t["active"]], "offer:", st["save_password"])
