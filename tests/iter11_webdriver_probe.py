# Probe navigator.webdriver / UA / brands in a group (default Main=1). Usage: python iter11_webdriver_probe.py [group]
import subprocess
import sys
import time

import requests
from dotenv import dotenv_values

API = dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
H = {"Authorization": "Bearer " + subprocess.check_output([sys.executable, "/app/tests/clerk_token.py", "shadow.a+clerk_test@example.com"], text=True).strip()}
g = sys.argv[1] if len(sys.argv) > 1 else "1"
html = ("data:text/html,<body><script>document.body.innerText='WD='+String(navigator.webdriver)+' UA='+navigator.userAgent"
        "+' BRANDS='+JSON.stringify((navigator.userAgentData||{}).brands)+' PLUG='+navigator.plugins.length+' LANG='+navigator.languages</script></body>")
print(requests.post(f"{API}/browser/navigate?group={g}", json={"url": html}, headers=H, timeout=60).status_code)
time.sleep(1)
requests.post(f"{API}/browser/input?group={g}", json={"kind": "key", "key": "Control+a"}, headers=H)
time.sleep(0.4)
print(requests.get(f"{API}/browser/selection?group={g}", headers=H).json())
