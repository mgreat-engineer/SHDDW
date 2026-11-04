"""Self-update for Shadow Helper from the project's public GitHub Releases."""
import asyncio
import hashlib
import json
import logging
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

log = logging.getLogger("shadow.updater")
CHECK_EVERY = 6 * 3600
IDLE_SECS = 600


def build_info():
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    try:
        return json.loads((base / "build_info.json").read_text())
    except Exception:
        return {"version": "0.0.0-dev", "repo": ""}


def parse_version(v):
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:3]) or (0,)


def asset_name():
    if sys.platform == "win32":
        return "ShadowHelper-Setup-Windows.exe"
    if sys.platform == "darwin":
        return "ShadowHelper-mac-apple-silicon.dmg" if platform.machine() == "arm64" else "ShadowHelper-mac-intel.dmg"
    return None


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "ShadowHelper-Updater", "Accept": "application/vnd.github+json"})
    return urllib.request.urlopen(req, timeout=timeout)


class Updater:
    def __init__(self, is_idle, on_status=lambda s: None, before_install=None):
        self.info = build_info()
        self.version = self.info.get("version", "0.0.0")
        self.repo = self.info.get("repo", "")
        self.is_idle = is_idle
        self.on_status = on_status
        self.before_install = before_install
        self.ready = None  # (version, installer path)

    @property
    def can_update(self):
        return bool(getattr(sys, "frozen", False) and self.repo and asset_name())

    def latest(self):
        with _get(f"https://api.github.com/repos/{self.repo}/releases/latest") as r:
            rel = json.load(r)
        assets = {a["name"]: a for a in rel.get("assets", [])}
        return rel.get("tag_name", ""), assets

    def download(self, tag, assets):
        name = asset_name()
        a, sums = assets.get(name), assets.get("checksums.txt")
        if not a or not sums:
            raise RuntimeError("release has no installer for this computer")
        with _get(sums["browser_download_url"]) as r:
            expected = dict(reversed(line.split()) for line in r.read().decode().splitlines() if line.strip()).get(name)
        dest = Path(tempfile.gettempdir()) / f"shadow-update-{parse_version(tag)[-1]}-{name}"
        h = hashlib.sha256()
        with _get(a["browser_download_url"], timeout=600) as r, open(dest, "wb") as f:
            for chunk in iter(lambda: r.read(1 << 20), b""):
                h.update(chunk)
                f.write(chunk)
        if not expected or h.hexdigest() != expected:
            dest.unlink(missing_ok=True)
            raise RuntimeError("downloaded update failed its checksum")
        return dest

    async def check(self, force=False):
        if not self.can_update:
            self.on_status(f"Version {self.version} (updates work in the installed app)")
            return
        if self.ready and not force:
            return
        try:
            tag, assets = await asyncio.to_thread(self.latest)
            if parse_version(tag) <= parse_version(self.version):
                self.on_status(f"Version {self.version} — up to date")
                return
            self.on_status(f"Downloading update {tag}…")
            path = await asyncio.to_thread(self.download, tag, assets)
            self.ready = (tag, path)
            self.on_status(f"Update {tag} ready — installs when Shadow is idle")
        except Exception as e:
            self.on_status(f"Version {self.version} — update check failed ({str(e)[:60]})")

    async def run(self):
        last = 0
        while True:
            if time.time() - last > CHECK_EVERY:
                last = time.time()
                await self.check()
            if self.ready and self.is_idle(IDLE_SECS):
                await self.install()
            await asyncio.sleep(60)

    async def install(self):
        tag, path = self.ready
        self.on_status(f"Installing update {tag}…")
        if self.before_install:
            await self.before_install()
        if sys.platform == "win32":
            flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
            subprocess.Popen([str(path), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"], creationflags=flags, close_fds=True)
        else:
            app = Path(sys.executable).resolve().parents[2]  # .../ShadowHelper.app
            script = f"""#!/bin/bash
while kill -0 {os.getpid()} 2>/dev/null; do sleep 1; done
MNT=$(mktemp -d)
hdiutil attach -nobrowse -quiet -mountpoint "$MNT" "{path}" || exit 1
rm -rf "{app}.old" && mv "{app}" "{app}.old" && ditto "$MNT/ShadowHelper.app" "{app}" && rm -rf "{app}.old" || {{ rm -rf "{app}"; mv "{app}.old" "{app}"; }}
hdiutil detach -quiet "$MNT"
open "{app}"
"""
            sp = Path(tempfile.gettempdir()) / "shadow-helper-update.sh"
            sp.write_text(script)
            sp.chmod(0o755)
            subprocess.Popen(["/bin/bash", str(sp)], start_new_session=True, close_fds=True)
        await asyncio.sleep(1)
        os._exit(0)
