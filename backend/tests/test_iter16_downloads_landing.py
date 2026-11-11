# Iteration 16: public downloads endpoint (live + unit w/ mocked GitHub) and desktop helper core (static)
import asyncio
import io
import json
import os
import sys
from unittest import mock

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    for line in open("/app/frontend/.env"):
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

sys.path[:0] = ["/app/backend", "/app/desktop", "/app/desktop/shadow_helper"]


# --- live public endpoint (HELPER_REPO empty) ---
def test_public_downloads_no_auth_unavailable():
    r = requests.get(f"{BASE_URL}/api/public/downloads", timeout=20)
    assert r.status_code == 200
    assert r.json() == {"available": False, "version": None, "links": {}}


def test_protected_still_401():
    r = requests.get(f"{BASE_URL}/api/status", timeout=20)
    assert r.status_code in (401, 403)


# --- unit: release parsing ---
@pytest.fixture
def server():
    import server as s
    s._DL_CACHE.update(t=0, data=None)
    yield s
    s._DL_CACHE.update(t=0, data=None)


REL = {"tag_name": "helper-v1.0.7", "assets": [
    {"name": "ShadowHelper-Setup-Windows.exe", "browser_download_url": "https://gh/x/win.exe"},
    {"name": "ShadowHelper-mac-apple-silicon.dmg", "browser_download_url": "https://gh/x/arm.dmg"},
    {"name": "ShadowHelper-mac-intel.dmg", "browser_download_url": "https://gh/x/intel.dmg"},
    {"name": "other.zip", "browser_download_url": "https://gh/x/other.zip"}]}


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_release_parsing(server, monkeypatch):
    monkeypatch.setenv("HELPER_REPO", "acme/shadow")
    calls = []

    def fake(req, timeout=None):
        calls.append(req.full_url)
        return _Resp(json.dumps(REL).encode())
    with mock.patch("urllib.request.urlopen", fake):
        d = asyncio.run(server.public_downloads())
        assert d["available"] is True
        assert d["version"] == "1.0.7"
        assert d["links"] == {"windows": "https://gh/x/win.exe", "mac_arm": "https://gh/x/arm.dmg", "mac_intel": "https://gh/x/intel.dmg"}
        assert calls == ["https://api.github.com/repos/acme/shadow/releases/latest"]
        # cached: second call no fetch
        d2 = asyncio.run(server.public_downloads())
        assert d2 == d and len(calls) == 1
        # expired cache -> refetch
        server._DL_CACHE["t"] -= 601
        asyncio.run(server.public_downloads())
        assert len(calls) == 2


def test_fetch_failure(server, monkeypatch):
    monkeypatch.setenv("HELPER_REPO", "acme/shadow")

    def boom(req, timeout=None):
        raise OSError("network down")
    with mock.patch("urllib.request.urlopen", boom):
        d = asyncio.run(server.public_downloads())
    assert d == {"available": False, "version": None, "links": {}}


def test_failure_is_cached_10min(server, monkeypatch):
    """Document behavior: does a failure get cached? (falsy-data check)"""
    monkeypatch.setenv("HELPER_REPO", "acme/shadow")
    n = []

    def boom(req, timeout=None):
        n.append(1)
        raise OSError("x")
    with mock.patch("urllib.request.urlopen", boom):
        asyncio.run(server.public_downloads())
        asyncio.run(server.public_downloads())
    print("fetch attempts after 2 calls on failure:", len(n))


def test_partial_assets(server, monkeypatch):
    monkeypatch.setenv("HELPER_REPO", "acme/shadow")
    rel = {"tag_name": "helper-v2.0.0", "assets": [REL["assets"][0]]}
    with mock.patch("urllib.request.urlopen", lambda req, timeout=None: _Resp(json.dumps(rel).encode())):
        d = asyncio.run(server.public_downloads())
    assert d["available"] is True and list(d["links"]) == ["windows"] and d["version"] == "2.0.0"


def test_empty_repo_env(server, monkeypatch):
    monkeypatch.setenv("HELPER_REPO", "  ")
    assert asyncio.run(server.public_downloads()) == {"available": False, "version": None, "links": {}}


# --- desktop helper core (static) ---
@pytest.fixture
def core(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    import core as c
    monkeypatch.setattr(c, "app_dir", lambda: tmp_path)
    return c


def _cfg(core, **kw):
    cfg = core.Config()
    cfg.data.update(kw)
    return cfg


def test_launch_options_headless(core):
    cfg = _cfg(core)
    assert cfg["show_browser"] is True
    assert core.launch_options(cfg)["headless"] is False
    cfg.data["show_browser"] = False
    assert core.launch_options(cfg)["headless"] is True


def test_open_app_window_chrome(core):
    cfg = _cfg(core, server_url="https://example.test/")
    with mock.patch.object(core, "find_chrome", return_value="/usr/bin/chrome"), \
         mock.patch("subprocess.Popen") as P, mock.patch("webbrowser.open") as W:
        core.open_app_window(cfg)
    args = P.call_args[0][0]
    assert args[0] == "/usr/bin/chrome"
    assert "--app=https://example.test/?app=1" in args
    assert any(a.startswith("--user-data-dir=") for a in args)
    W.assert_not_called()


def test_open_app_window_default_url(core):
    cfg = _cfg(core, server_url="")
    with mock.patch.object(core, "find_chrome", return_value="chrome"), mock.patch("subprocess.Popen") as P:
        core.open_app_window(cfg)
    assert "--app=https://shddw.com/?app=1" in P.call_args[0][0]


def test_open_app_window_fallback(core):
    cfg = _cfg(core, server_url="")
    with mock.patch.object(core, "find_chrome", return_value=None), \
         mock.patch("subprocess.Popen") as P, mock.patch("webbrowser.open") as W:
        core.open_app_window(cfg)
    W.assert_called_once_with("https://shddw.com/?app=1")
    P.assert_not_called()
