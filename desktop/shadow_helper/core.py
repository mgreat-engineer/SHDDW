"""Shadow Helper core: pairs with a Shadow account and runs a hidden Chrome on this computer."""
import asyncio
import base64
import json
import logging
import os
import platform
import shutil
import sys
import time
import urllib.request
from pathlib import Path

import websockets

from shadow_browser import BrowserSession, read_file_text, unique_path
from updater import build_info

VERSION = build_info().get("version", "0.0.0-dev")
log = logging.getLogger("shadow.helper")

ALLOWED = {"state", "frame", "input", "nav", "navigate", "tabs", "resolve_dialog", "upload", "cancel_chooser",
           "record_start", "record_note", "record_stop", "corrections_start", "corrections_take", "take_events",
           "clear_events", "elements", "page_text", "act", "current_url", "files_list", "file_read", "file_write",
           "highlight", "unhighlight", "groups_list", "group_new", "group_rename", "group_close",
           "take_credential", "dismiss_credential", "fill_login", "selection_text",
           "groups_restore", "save_states"}
GROUP_ADMIN = {"groups_list", "group_new", "group_rename", "group_close", "groups_restore", "save_states"}
PASSIVE = {"state", "frame", "current_url", "files_list", "take_events", "clear_events"}


def app_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home())) / "ShadowHelper"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "ShadowHelper"
    else:
        base = Path.home() / ".shadow-helper"
    base.mkdir(parents=True, exist_ok=True)
    return base


def chrome_user_data() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "User Data"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
    return Path.home() / ".config" / "google-chrome"


def read_chrome_bookmarks(limit=2000):
    """Read the user's Chrome bookmarks (every profile) as [{title, url, folder}] — read-only."""
    out, seen = [], set()
    root = chrome_user_data()
    files = sorted(root.glob("*/Bookmarks")) if root.exists() else []
    if not files:
        raise ValueError("Couldn't find Chrome bookmarks on this computer")

    def walk(node, path):
        if len(out) >= limit:
            return
        if node.get("type") == "url":
            url = node.get("url", "")
            if url.startswith(("http://", "https://")) and url not in seen:
                seen.add(url)
                out.append({"title": node.get("name") or url, "url": url, "folder": " / ".join(path)[:60]})
        for ch in node.get("children", []) or []:
            walk(ch, path + [ch["name"]] if ch.get("type") == "folder" else path)

    for f in files:
        try:
            roots = json.loads(f.read_text(encoding="utf-8")).get("roots", {})
        except Exception:
            continue
        walk(roots.get("bookmark_bar", {}), [])
        walk(roots.get("other", {}), ["Other bookmarks"])
        walk(roots.get("synced", {}), ["Mobile bookmarks"])
    return out


class Config:
    def __init__(self):
        self.path = app_dir() / "config.json"
        default_dl = Path.home() / "Downloads" / "Shadow"
        self.data = {"server_url": "", "token": "", "device_name": platform.node() or "My laptop",
                     "folders": [str(default_dl)], "downloads_folder": str(default_dl), "use_chrome_logins": True,
                     "show_browser": True, "open_app_on_start": True}
        if self.path.exists():
            try:
                self.data.update(json.loads(self.path.read_text()))
            except Exception:
                pass

    def __getitem__(self, k):
        return self.data.get(k)

    def __setitem__(self, k, v):
        self.data[k] = v
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.data, indent=2))


def decode_connection_code(code: str):
    """Connection code = base64url(JSON {u: server url, c: pairing code})."""
    code = code.strip()
    pad = "=" * (-len(code) % 4)
    data = json.loads(base64.urlsafe_b64decode(code + pad).decode())
    return data["u"].rstrip("/"), data["c"]


def pair(cfg: Config, connection_code: str):
    url, code = decode_connection_code(connection_code)
    body = json.dumps({"code": code, "name": cfg["device_name"]}).encode()
    req = urllib.request.Request(url + "/api/helper/pair", data=body, method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": f"ShadowHelper/{VERSION}"})
    try:
        res = json.load(urllib.request.urlopen(req, timeout=30))
    except urllib.error.HTTPError as e:
        detail = e.read().decode()
        try:
            detail = json.loads(detail).get("detail", detail)
        except Exception:
            pass
        raise RuntimeError(detail)
    cfg.data.update({"server_url": url, "token": res["token"]})
    cfg.save()
    return res


def copy_chrome_logins(dest_profile: Path):
    """Copy the person's last-used Chrome profile (logins/cookies) into Shadow's own profile folder."""
    src_root = chrome_user_data()
    if not (src_root / "Local State").exists():
        raise RuntimeError("Google Chrome profile not found on this computer")
    try:
        last = json.loads((src_root / "Local State").read_text(errors="ignore")).get("profile", {}).get("last_used") or "Default"
    except Exception:
        last = "Default"
    src = src_root / last
    if not src.exists():
        src = src_root / "Default"
    skip = shutil.ignore_patterns("Cache", "Code Cache", "GPUCache", "Service Worker", "CacheStorage", "Crashpad",
                                  "*.log", "LOCK", "SingletonLock", "DawnCache", "GrShaderCache", "ShaderCache")
    if dest_profile.exists():
        shutil.rmtree(dest_profile, ignore_errors=True)
    dest_profile.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_root / "Local State", dest_profile / "Local State")
    failed = []

    def copy_fn(s, d):
        try:
            shutil.copy2(s, d)
        except Exception:
            failed.append(Path(s).name)
    shutil.copytree(src, dest_profile / "Default", ignore=skip, copy_function=copy_fn, dirs_exist_ok=True)
    return {"profile": last, "skipped": failed}


class LocalFolders:
    """Files area = only the folders the person picked."""

    def __init__(self, cfg: Config):
        self.cfg = cfg

    def roots(self):
        out = {}
        for f in self.cfg["folders"] or []:
            p = Path(f)
            label = p.name or str(p)
            while label in out:
                label += "_"
            out[label] = p
        return out

    def _inside(self, name: str, must_exist=True) -> Path:
        label, _, rel = name.partition("/")
        roots = self.roots()
        if label not in roots or not rel:
            raise ValueError(f"'{name}' is not inside a folder you allowed")
        root = roots[label].resolve()
        p = (root / rel).resolve()
        if root != p and root not in p.parents:
            raise ValueError("That path is outside your allowed folders")
        if must_exist and not p.is_file():
            raise ValueError(f"File not found: {name}")
        return p

    async def list(self):
        out = []
        for label, root in self.roots().items():
            if not root.exists():
                continue
            for p in sorted(root.rglob("*")):
                if len(out) >= 500:
                    return out
                if p.is_file() and not p.name.startswith(".") and len(p.relative_to(root).parts) <= 3:
                    out.append({"name": f"{label}/{p.relative_to(root).as_posix()}", "size": p.stat().st_size, "source": "laptop"})
        return out

    async def resolve(self, name):
        return self._inside(name)

    async def download_path(self, suggested):
        d = Path(self.cfg["downloads_folder"] or (self.cfg["folders"] or [str(app_dir() / "Downloads")])[0])
        d.mkdir(parents=True, exist_ok=True)
        return unique_path(d, suggested)

    async def downloaded(self, p):
        return None

    async def read(self, name):
        try:
            return read_file_text(self._inside(name))
        except ValueError as e:
            return f"ERROR: {e}"

    async def write(self, name, content):
        if "/" in name:
            p = self._inside(name, must_exist=False)
        else:
            p = await self.download_path(name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"Saved {p}"


APP_URL = "https://shddw.com"


def find_chrome():
    if sys.platform == "win32":
        for base in (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")):
            p = Path(base or "") / "Google" / "Chrome" / "Application" / "chrome.exe"
            if base and p.exists():
                return str(p)
    elif sys.platform == "darwin":
        p = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        if p.exists():
            return str(p)
    return shutil.which("google-chrome") or shutil.which("google-chrome-stable") or shutil.which("chromium")


def open_app_window(cfg: Config):
    """Open Shadow's interface in its own app window (Chrome app mode, no tabs or address bar)."""
    import subprocess
    import webbrowser
    url = (cfg["server_url"] or APP_URL).rstrip("/")
    exe = find_chrome()
    if not exe:
        webbrowser.open(url + "/?app=1")
        return
    subprocess.Popen([exe, f"--app={url}/?app=1", f"--user-data-dir={app_dir() / 'app-window'}", "--no-first-run",
                      "--no-default-browser-check", "--window-size=1440,920"], close_fds=True)


def launch_options(cfg: Config):
    opts = {"channel": "chrome"}
    if os.environ.get("SHADOW_CHROME_PATH"):
        opts = {"executable_path": os.environ["SHADOW_CHROME_PATH"]}
    opts["headless"] = not cfg["show_browser"]
    if cfg["use_chrome_logins"]:
        # Let Chrome use the real OS keychain so copied logins can be decrypted.
        if sys.platform == "darwin":
            opts["ignore_default_args"] = ["--use-mock-keychain"]
        elif sys.platform.startswith("linux"):
            opts["ignore_default_args"] = ["--password-store=basic"]
    return opts


class Helper:
    def __init__(self, cfg: Config, on_status=lambda s: None):
        self.cfg = cfg
        self.on_status = on_status
        self.session = None
        self.ws = None
        self.stop_flag = False
        self.browser_lock = asyncio.Lock()
        self.last_work = time.time()

    def is_idle(self, secs):
        recording = bool(self.session and self.session.recording is not None)
        return not recording and time.time() - self.last_work > secs

    def info(self):
        return {"version": VERSION, "os": f"{platform.system()} {platform.release()}", "folders": self.cfg["folders"],
                "downloads_folder": self.cfg["downloads_folder"], "chrome_logins": bool(self.cfg["use_chrome_logins"]),
                "browser_ready": bool(self.session)}

    async def ensure_browser(self):
        async with self.browser_lock:
            if self.session and not self.session.closed:
                return self.session
            s = BrowserSession(LocalFolders(self.cfg), app_dir() / "chrome-profile", launch_options(self.cfg))
            await s.start()
            self.session = s
            return s

    async def restart_browser(self):
        if self.session:
            try:
                await self.session.close()
            except Exception:
                pass
        self.session = None

    async def send_hello(self):
        if self.ws:
            try:
                await self.ws.send(json.dumps({"event": "hello", "info": self.info()}))
            except Exception:
                pass

    async def handle(self, msg):
        mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
        try:
            if method not in ALLOWED and method != "chrome_bookmarks":
                raise ValueError(f"Not allowed: {method}")
            if method == "chrome_bookmarks":
                res = read_chrome_bookmarks()
                await self.ws.send(json.dumps({"id": mid, "result": res}, default=str))
                return
            if method not in PASSIVE:
                self.last_work = time.time()
            s = await self.ensure_browser()
            s.touch()
            gid = params.pop("group", "1")
            res = await getattr(s if method in GROUP_ADMIN else s.group(gid), method)(**params)
            if method == "frame":
                res = base64.b64encode(res).decode() if res else None
            out = {"id": mid, "result": res}
        except Exception as e:
            out = {"id": mid, "error": str(e)[:400] or e.__class__.__name__}
        try:
            await self.ws.send(json.dumps(out, default=str))
        except Exception:
            pass

    async def run(self):
        delay = 2
        while not self.stop_flag:
            if not self.cfg["token"]:
                self.on_status("Not linked — paste a connection code")
                await asyncio.sleep(2)
                continue
            url = self.cfg["server_url"].replace("https://", "wss://").replace("http://", "ws://") + "/api/helper/ws"
            try:
                self.on_status("Connecting…")
                async with websockets.connect(url, additional_headers={"Authorization": "Bearer " + self.cfg["token"]},
                                              max_size=32 * 1024 * 1024, ping_interval=20, ping_timeout=40) as ws:
                    self.ws = ws
                    delay = 2
                    self.on_status("Connected — Shadow can use this computer")
                    await self.ensure_browser()
                    await self.send_hello()
                    async for raw in ws:
                        asyncio.ensure_future(self.handle(json.loads(raw)))
                    if ws.close_code == 4401:
                        self.cfg["token"] = ""
                        self.on_status("This computer was unlinked — paste a new connection code")
            except Exception as e:
                code = getattr(getattr(e, "rcvd", None), "code", None)
                if code == 4401:
                    self.cfg["token"] = ""
                    self.on_status("This computer was unlinked — paste a new connection code")
                else:
                    self.on_status(f"Offline, retrying in {delay}s ({str(e)[:60]})")
            self.ws = None
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)
