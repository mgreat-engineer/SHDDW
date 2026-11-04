"""Offline test of the helper updater: version compare, checksum-verified download, idle gating."""
import asyncio
import hashlib
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "/app/desktop/shadow_helper")
sys.path.insert(0, "/app/backend")
import updater  # noqa: E402

tmp = Path(tempfile.mkdtemp())
payload = b"fake-installer-bytes" * 1000
(tmp / "ShadowHelper-Setup-Windows.exe").write_bytes(payload)


def make_release(good=True):
    digest = hashlib.sha256(payload if good else b"x").hexdigest()
    (tmp / "checksums.txt").write_text(f"{digest}  ShadowHelper-Setup-Windows.exe\n{'0' * 64}  ShadowHelper-mac-intel.dmg\n")
    rel = {"tag_name": "helper-v1.0.42", "assets": [
        {"name": n, "browser_download_url": (tmp / n).as_uri()} for n in ("ShadowHelper-Setup-Windows.exe", "checksums.txt")]}
    (tmp / "latest.json").write_text(json.dumps(rel))


real_get = updater._get
updater._get = lambda url, timeout=30: real_get((tmp / "latest.json").as_uri() if url.startswith("https://api.github.com") else url, timeout)
updater.asset_name = lambda: "ShadowHelper-Setup-Windows.exe"
updater.sys.frozen = True


def run(good, version="1.0.7"):
    make_release(good)
    msgs = []
    u = updater.Updater(lambda s: False, on_status=msgs.append)
    u.version, u.repo = version, "someone/shadow"
    asyncio.run(u.check(force=True))
    return u, msgs


assert updater.parse_version("helper-v1.0.42") == (1, 0, 42)
assert updater.parse_version("1.0.42") > updater.parse_version("1.0.7")
u, msgs = run(True)
assert u.ready and u.ready[0] == "helper-v1.0.42" and Path(u.ready[1]).read_bytes() == payload, msgs
print("newer + good checksum ->", msgs[-1])
u, msgs = run(False)
assert not u.ready and "checksum" in msgs[-1], msgs
print("bad checksum ->", msgs[-1])
u, msgs = run(True, version="1.0.42")
assert not u.ready and "up to date" in msgs[-1], msgs
print("same version ->", msgs[-1])

sys.path.insert(0, "/app/desktop/shadow_helper")
import core  # noqa: E402
h = core.Helper.__new__(core.Helper)
h.session, h.last_work = None, 0
assert h.is_idle(600)
h.last_work = __import__("time").time()
assert not h.is_idle(600)
print("idle gating ok")
print("ALL UPDATER TESTS PASSED")
