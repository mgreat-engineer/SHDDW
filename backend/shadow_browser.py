import asyncio
import logging
import sys
import time
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, urlparse
from playwright.async_api import async_playwright

log = logging.getLogger("shadow.browser")

DATA_DIR = Path(__file__).resolve().parent.parent / "shadow_data"
VIEWPORT = {"width": 1280, "height": 800}
_pw = None
_pw_lock = asyncio.Lock()
_sessions: dict = {}
_sessions_lock = asyncio.Lock()

RECORDER_JS = r"""
(() => {
  if (window.__shadowRecInstalled) return; window.__shadowRecInstalled = true;
  const desc = (el) => {
    if (!el || !el.tagName) return {};
    const t = el.closest('a,button,input,textarea,select,[role],label,summary') || el;
    return {tag: t.tagName.toLowerCase(), type: t.type || '', role: t.getAttribute('role') || '',
      text: (t.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 80),
      label: t.getAttribute('aria-label') || t.placeholder || t.name || t.title || t.id || '',
      href: t.href || ''};
  };
  const val = (t) => t.type === 'password' ? '[hidden password]' :
    (t.type === 'file' ? [...(t.files || [])].map(f => f.name).join(', ') : (t.value || '').slice(0, 300));
  const send = (kind, el, extra) => {
    try { window.__shadowRecord && window.__shadowRecord(JSON.stringify(Object.assign({kind, el: desc(el), url: location.href, title: document.title}, extra || {}))); } catch (e) {}
  };
  document.addEventListener('click', e => send('click', e.target), true);
  document.addEventListener('change', e => { const t = e.target; if (t && t.tagName) send('input', t, {value: val(t)}); }, true);
  document.addEventListener('keydown', e => {
    if (['Enter', 'Tab', 'Escape'].includes(e.key)) send('key', e.target, {key: e.key, value: e.target && e.target.tagName ? val(e.target) : ''});
  }, true);
  document.addEventListener('submit', e => send('submit', e.target), true);
})();
"""

CRED_JS = r"""
(() => {
  if (window.__shadowCredInstalled) return; window.__shadowCredInstalled = true;
  const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 1 && r.height > 1; };
  let last = 0;
  const grab = () => {
    const pw = [...document.querySelectorAll('input[type=password]')].find(e => e.value && vis(e));
    if (!pw || Date.now() - last < 800) return; last = Date.now();
    const scope = pw.form || document;
    const users = [...scope.querySelectorAll('input[type=email],input[type=text],input[type=tel],input:not([type])')]
      .filter(e => e.value && vis(e) && (e.compareDocumentPosition(pw) & Node.DOCUMENT_POSITION_FOLLOWING));
    const u = users.length ? users[users.length - 1].value : (sessionStorage.getItem('__shadowUser') || '');
    try { window.__shadowCred && window.__shadowCred(JSON.stringify({origin: location.origin, username: u, password: pw.value})); } catch (e) {}
  };
  const rememberUser = (t) => { if (t && t.tagName === 'INPUT' && /^(email|text|tel)$/.test(t.type || 'text') && t.value && (t.autocomplete || '').includes('username') || (t && t.type === 'email' && t.value)) sessionStorage.setItem('__shadowUser', t.value); };
  document.addEventListener('submit', grab, true);
  document.addEventListener('change', e => rememberUser(e.target), true);
  document.addEventListener('keydown', e => { if (e.key === 'Enter') { rememberUser(e.target); grab(); } }, true);
  document.addEventListener('click', e => { const b = e.target.closest && e.target.closest('button,input[type=submit],[role=button]'); if (b) grab(); }, true);
})();
"""

FILL_JS = r"""
([username, password]) => {
  const vis = (e) => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e); return r.width > 1 && r.height > 1 && s.visibility !== 'hidden'; };
  const set = (el, v) => {
    el.focus();
    const proto = Object.getPrototypeOf(el);
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, v);
    el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true}));
  };
  const pw = [...document.querySelectorAll('input[type=password]')].find(vis);
  const scope = (pw && pw.form) || document;
  const cands = [...scope.querySelectorAll('input[type=email],input[type=text],input[type=tel],input:not([type])')].filter(vis)
    .filter(e => !pw || (e.compareDocumentPosition(pw) & Node.DOCUMENT_POSITION_FOLLOWING));
  const user = cands.find(e => /user|email|login|account/i.test((e.autocomplete || '') + e.name + e.id + (e.placeholder || ''))) || cands[cands.length - 1];
  const done = [];
  if (user && username) { set(user, username); done.push('username'); }
  if (pw) { set(pw, password); done.push('password'); }
  return done;
}
"""

SELECTION_JS = r"""
() => {
  const a = document.activeElement;
  if (a && (a.tagName === 'TEXTAREA' || (a.tagName === 'INPUT' && a.type !== 'password')) && a.selectionStart !== a.selectionEnd)
    return a.value.slice(a.selectionStart, a.selectionEnd);
  return String(window.getSelection() || '');
}
"""

STEALTH_JS = r"""
(() => {
  try { Object.defineProperty(Navigator.prototype, 'webdriver', {get: () => undefined}); } catch (e) {}
  try { if (!window.chrome) window.chrome = {runtime: {}, app: {isInstalled: false}}; } catch (e) {}
  try { Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']}); } catch (e) {}
  try { if (!navigator.plugins.length) Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]}); } catch (e) {}
  try {
    const q = navigator.permissions && navigator.permissions.query;
    if (q) navigator.permissions.query = (p) => p && p.name === 'notifications' ? Promise.resolve({state: Notification.permission}) : q.call(navigator.permissions, p);
  } catch (e) {}
})();
"""

HIGHLIGHT_JS = r"""
([id, x, y, label]) => {
  const old = document.getElementById('__shadow_hl'); if (old) old.remove();
  let r;
  if (id) { const el = document.querySelector(`[data-shadow-id="${id}"]`); if (!el) return false; r = el.getBoundingClientRect(); }
  else if (x != null) r = {left: x - 16, top: y - 16, width: 32, height: 32};
  else return false;
  const d = document.createElement('div'); d.id = '__shadow_hl';
  d.style.cssText = `position:fixed;left:${r.left - 4}px;top:${r.top - 4}px;width:${r.width + 8}px;height:${r.height + 8}px;border:3px solid #FF3B30;border-radius:6px;box-shadow:0 0 0 9999px rgba(0,0,0,0.28);z-index:2147483647;pointer-events:none;`;
  const t = document.createElement('div'); t.textContent = label;
  t.style.cssText = `position:absolute;left:0;${r.top > 34 ? 'top:-28px' : 'bottom:-28px'};background:#FF3B30;color:#fff;font:600 12px sans-serif;padding:4px 8px;border-radius:4px;white-space:nowrap;`;
  d.appendChild(t); document.documentElement.appendChild(d); return true;
}
"""

ELEMENTS_JS = r"""
() => {
  const sel = 'a,button,input,textarea,select,[role=button],[role=link],[role=tab],[role=menuitem],[role=checkbox],[role=radio],[role=option],[role=combobox],[role=switch],[onclick],[contenteditable=true],summary,label';
  document.querySelectorAll('[data-shadow-id]').forEach(e => e.removeAttribute('data-shadow-id'));
  const out = []; let i = 0;
  for (const el of document.querySelectorAll(sel)) {
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) continue;
    if (r.bottom < 0 || r.top > innerHeight || r.right < 0 || r.left > innerWidth) continue;
    const st = getComputedStyle(el);
    if (st.visibility === 'hidden' || st.display === 'none' || +st.opacity === 0) continue;
    i++; el.setAttribute('data-shadow-id', String(i));
    const isPw = el.type === 'password';
    out.push({id: i, tag: el.tagName.toLowerCase(), type: el.type || '', role: el.getAttribute('role') || '',
      text: (el.innerText || (isPw ? '' : el.value) || '').trim().replace(/\s+/g, ' ').slice(0, 70),
      label: (el.getAttribute('aria-label') || el.placeholder || el.name || el.title || '').slice(0, 50),
      href: (el.getAttribute('href') || '').slice(0, 80), checked: el.checked === true,
      x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2)});
    if (i >= 160) break;
  }
  return out;
}
"""


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def safe_name(name: str) -> str:
    name = re.sub(r"[^\w.\- ()]+", "_", name or "file").strip() or "file"
    return name[:150]


def user_dir(user_id: str, kind: str) -> Path:
    d = DATA_DIR / kind / safe_name(user_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def describe_event(ev: dict) -> str:
    el = ev.get("el") or {}
    who = el.get("text") or el.get("label") or el.get("href") or el.get("tag") or "element"
    k = ev.get("kind")
    if k == "click":
        return f'Clicked "{who}" ({el.get("tag", "")}) on {ev.get("title") or ev.get("url", "")}'
    if k == "input":
        return f'Entered "{ev.get("value", "")}" into "{el.get("label") or who}"'
    if k == "key":
        return f'Pressed {ev.get("key")} in "{el.get("label") or who}"' + (f' (value "{ev["value"]}")' if ev.get("value") else "")
    if k == "submit":
        return f'Submitted form on {ev.get("title") or ev.get("url", "")}'
    if k == "navigate":
        return f'Page loaded: {ev.get("url")}'
    if k == "note":
        return f'USER NOTE: {ev.get("text")}'
    return ev.get("text") or k or "event"


async def get_playwright():
    global _pw
    async with _pw_lock:
        if _pw is None:
            _pw = await async_playwright().start()
        return _pw


def read_file_text(p: Path) -> str:
    if p.suffix.lower() in (".xlsx", ".xlsm"):
        import openpyxl
        wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
        out = []
        for ws in wb.worksheets:
            out.append(f"# Sheet {ws.title}")
            for row in ws.iter_rows(values_only=True):
                out.append(",".join("" if v is None else str(v) for v in row))
        return "\n".join(out)[:20000]
    try:
        return p.read_text(errors="replace")[:20000]
    except Exception as e:
        return f"Cannot read file: {e}"


def unique_path(d: Path, name: str) -> Path:
    target = d / safe_name(name)
    if target.exists():
        target = d / f"{target.stem}-{uuid.uuid4().hex[:5]}{target.suffix}"
    return target


class CloudFiles:
    """Files area stored on the server for one user."""
    def __init__(self, user_id, db):
        self.user_id, self.db = user_id, db

    def _dir(self):
        return user_dir(self.user_id, "files")

    async def list(self):
        docs = await self.db.files.find({"user_id": self.user_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
        return [{"name": d["name"], "size": d.get("size", 0), "source": d.get("source", "")} for d in docs]

    async def resolve(self, name):
        p = self._dir() / safe_name(name)
        if not p.exists():
            raise ValueError(f"File not found in Files: {name}")
        return p

    async def download_path(self, suggested):
        return unique_path(self._dir(), suggested)

    async def _record(self, p: Path, source):
        await self.db.files.update_one({"user_id": self.user_id, "name": p.name}, {"$set": {
            "size": p.stat().st_size, "source": source, "created_at": now_iso()},
            "$setOnInsert": {"id": str(uuid.uuid4())}}, upsert=True)

    async def downloaded(self, p: Path):
        await self._record(p, "download")

    async def read(self, name):
        p = self._dir() / safe_name(name)
        return read_file_text(p) if p.exists() else f"File not found: {name}"

    async def write(self, name, content):
        p = self._dir() / safe_name(name)
        p.write_text(content)
        await self._record(p, "generated")
        return f"Saved {p.name}"


MAX_GROUPS = 10


class Group:
    """One workspace: its own browser context (logins, cookies, history), tabs, dialogs, recording and task."""
    def __init__(self, browser, gid: str, name: str, ctx, label: str = ""):
        self.b = browser
        self.ctx = ctx
        self.id = gid
        self.name = name
        self.label = label or ""
        self.files = browser.files
        self.own = []
        self.active = 0
        self.recording = None
        self.correction_sink = None
        self.pending_dialog = None
        self.pending_chooser = None
        self.events = []
        self.last_frame = None
        self.viewport = dict(VIEWPORT)
        self.pending_cred = None

    async def set_viewport(self, width, height):
        vp = {"width": max(640, min(int(width), 2560)), "height": max(400, min(int(height), 1600))}
        for p in self.pages():
            if p.viewport_size != vp:
                try:
                    await p.set_viewport_size(vp)
                except Exception:
                    pass
        self.viewport = vp
        return vp

    @property
    def closed(self):
        return self.b.closed or self.id not in self.b.groups

    def touch(self):
        self.b.touch()

    def info(self):
        ps = self.pages()
        p = ps[max(0, min(self.active, len(ps) - 1))] if ps else None
        return {"id": self.id, "name": self.name, "label": self.label, "tabs": len(ps), "url": p.url if p else "",
                "urls": [x.url for x in ps if x.url not in ("", "about:blank")][:20], "active": self.active,
                "recording": self.recording is not None}

    async def attach(self):
        await self.ctx.expose_binding("__shadowRecord", self._on_record)
        await self.ctx.expose_binding("__shadowCred", self._on_cred)
        await self.ctx.add_init_script(RECORDER_JS)
        await self.ctx.add_init_script(CRED_JS)
        if self.b.ua:
            await self.ctx.add_init_script(STEALTH_JS)
        self.ctx.on("page", self._on_popup)
        for p in self.ctx.pages:
            self.adopt(p)

    async def _on_cred(self, source, payload):
        import json
        try:
            c = json.loads(payload)
            if c.get("password") and c.get("origin", "").startswith("http"):
                self.pending_cred = {"origin": c["origin"].lower(), "username": str(c.get("username") or "")[:200], "password": c["password"][:500]}
        except Exception:
            return

    async def _apply_ua(self, page):
        ua = self.b.ua
        if getattr(page, "_shadow_ua", None):
            return
        try:
            cdp = await self.ctx.new_cdp_session(page)
            await cdp.send("Network.setUserAgentOverride", {"userAgent": ua["ua"], "acceptLanguage": "en-US,en;q=0.9", "platform": "Linux x86_64",
                                                             "userAgentMetadata": ua["meta"]})
            page._shadow_ua = cdp  # keep the session alive: the override lasts only while it is attached
        except Exception:
            pass

    async def take_credential(self):
        c, self.pending_cred = self.pending_cred, None
        return c

    async def dismiss_credential(self):
        self.pending_cred = None
        return True

    async def fill_login(self, username, password):
        page = await self.ensure_page()
        done = await asyncio.wait_for(page.evaluate(FILL_JS, [username, password]), 6)
        if not done:
            raise ValueError("No login form found on this page")
        self.capture({"kind": "browser", "text": "Filled saved login" + (f" for {username}" if username else "")})
        return "Filled " + " and ".join(done)

    async def selection_text(self):
        page = self.page()
        if not page:
            return ""
        try:
            return (await asyncio.wait_for(page.evaluate(SELECTION_JS), 3))[:200000]
        except Exception:
            return ""

    async def _on_record(self, source, payload):
        import json
        try:
            self.capture(json.loads(payload))
        except Exception:
            return

    async def open_urls(self, urls, active=0, reuse_first=False):
        for i, u in enumerate(urls):
            try:
                if i == 0 and reuse_first:
                    await self.navigate(u)
                else:
                    await self.new_tab(u)
            except Exception as e:
                log.warning("reopen tab %s: %s", u, e)
        self.active = max(0, min(int(active or 0), len(self.pages()) - 1))

    async def run_guarded(self, coro, timeout=30):
        """Run a browser action; return early (success) if it opened a JS dialog that now blocks it."""
        before = self.pending_dialog
        task = asyncio.ensure_future(coro)
        end = time.time() + timeout
        while time.time() < end:
            if task.done():
                return task.result()
            if self.pending_dialog and self.pending_dialog is not before:
                task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
                return f'Action opened a {self.pending_dialog.type} dialog: "{self.pending_dialog.message}"'
            await asyncio.sleep(0.2)
        task.cancel()
        raise TimeoutError(f"Action did not finish within {timeout}s")

    # ---------- events ----------
    def capture(self, ev: dict):
        ev = {**ev, "t": now_iso()}
        ev["desc"] = describe_event(ev)
        for sink in (self.recording, self.correction_sink):
            if sink is None:
                continue
            if sink and sink[-1].get("desc") == ev["desc"]:
                continue
            sink.append(ev)

    def push_event(self, text: str):
        self.events.append(text)
        self.events = self.events[-30:]
        self.capture({"kind": "browser", "text": text})

    def adopt(self, page, focus=True):
        if page not in self.b.owner:
            self.b.owner[page] = self
            self.own.append(page)
            page.on("dialog", self._on_dialog)
            page.on("download", self._on_download)
            page.on("filechooser", self._on_chooser)
            page.on("framenavigated", lambda fr, p=page: self._on_nav(p, fr))
            page.on("close", self._on_page_close)
            if self.b.ua:
                asyncio.ensure_future(self._apply_ua(page))
            if self.viewport != VIEWPORT:
                asyncio.ensure_future(page.set_viewport_size(self.viewport))
        if focus:
            self.active = self.pages().index(page) if not page.is_closed() else self.active

    def _on_popup(self, page):
        if page in self.b.owner:
            return
        self.adopt(page)
        self.push_event(f"Opened new tab {page.url}")

    def _on_page_close(self, page):
        self.b.owner.pop(page, None)
        if page in self.own:
            self.own.remove(page)
        self.pending_dialog = None
        self.pending_chooser = None

    def _on_nav(self, page, frame):
        if frame == page.main_frame:
            self.pending_dialog = None
            self.pending_chooser = None
        if frame == page.main_frame and frame.url not in ("about:blank", ""):
            self.capture({"kind": "navigate", "url": frame.url})
        if frame == page.main_frame and "google." in frame.url and "/sorry/" in frame.url:
            cont = (parse_qs(urlparse(frame.url).query).get("continue") or [""])[0]
            q = (parse_qs(urlparse(cont).query).get("q") or [""])[0]
            if q:
                self.push_event("Google blocked this search as unusual traffic — searched on Bing instead")
                asyncio.ensure_future(page.goto("https://www.bing.com/search?q=" + quote_plus(q), wait_until="domcontentloaded", timeout=30000))

    async def _on_dialog(self, dialog):
        self.pending_dialog = dialog
        self.push_event(f'Dialog appeared ({dialog.type}): "{dialog.message}"')

    def _on_chooser(self, chooser):
        self.pending_chooser = chooser
        self.push_event("File picker opened (waiting for a file to be chosen)")

    async def _on_download(self, download):
        try:
            target = await self.files.download_path(download.suggested_filename)
            await download.save_as(str(target))
            await self.files.downloaded(target)
        except Exception as e:
            self.push_event(f"Download failed: {e}")
            return
        self.push_event(f"Downloaded file {target.name}")

    # ---------- tabs ----------
    def pages(self):
        return [p for p in self.own if not p.is_closed()]

    def page(self):
        ps = self.pages()
        if not ps:
            return None
        self.active = max(0, min(self.active, len(ps) - 1))
        return ps[self.active]

    async def ensure_page(self):
        if self.closed:
            raise ValueError("This workspace was closed")
        if not self.pages():
            self.adopt(await self.ctx.new_page())
        return self.page()

    async def state(self):
        tabs = []
        for i, p in enumerate(self.pages()):
            try:
                title = await asyncio.wait_for(p.title(), 1.5)
            except Exception:
                title = ""
            tabs.append({"index": i, "url": p.url, "title": title or p.url, "active": i == self.active})
        dlg = self.pending_dialog
        cred = self.pending_cred
        page = self.page()
        has_pw = False
        if page and not dlg:
            try:
                has_pw = await asyncio.wait_for(page.evaluate("() => !!document.querySelector('input[type=password]')"), 1)
            except Exception:
                pass
        import hashlib
        return {
            "group": {"id": self.id, "name": self.name, "label": self.label},
            "tabs": tabs,
            "recording": self.recording is not None,
            "recorded": [e["desc"] for e in (self.recording or [])][-8:],
            "recorded_count": len(self.recording or []),
            "dialog": {"type": dlg.type, "message": dlg.message, "default": dlg.default_value} if dlg else None,
            "file_chooser": bool(self.pending_chooser),
            "viewport": self.viewport,
            "has_password_field": has_pw,
            "save_password": {"origin": cred["origin"], "username": cred["username"],
                              "pw_sha": hashlib.sha256(cred["password"].encode()).hexdigest()} if cred else None,
        }

    async def frame(self, quality=60):
        page = await self.ensure_page()
        try:
            self.last_frame = await page.screenshot(type="jpeg", quality=quality, timeout=4000)
        except Exception:
            pass
        return self.last_frame

    async def stream(self, send, alive, quality=70):
        """Push live JPEG frames of the active tab via Chrome's screencast (follows tab switches)."""
        import base64
        cur, cdp = None, None

        async def on_frame(c, ev):
            try:
                await send(base64.b64decode(ev["data"]))
            except Exception:
                pass
            finally:
                try:
                    await c.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]})
                except Exception:
                    pass

        async def stop():
            if cdp:
                try:
                    await cdp.send("Page.stopScreencast")
                    await cdp.detach()
                except Exception:
                    pass
        try:
            while alive():
                page = self.page()
                key = (page, self.viewport["width"], self.viewport["height"])
                if key != cur:
                    await stop()
                    cur, cdp = key, None
                    if page:
                        if page.viewport_size != self.viewport:
                            try:
                                await page.set_viewport_size(self.viewport)
                            except Exception:
                                pass
                        try:
                            await send(await page.screenshot(type="jpeg", quality=quality, timeout=4000))
                        except Exception:
                            pass
                        cdp = await self.ctx.new_cdp_session(page)
                        cdp.on("Page.screencastFrame", lambda ev, c=cdp: asyncio.ensure_future(on_frame(c, ev)))
                        await cdp.send("Page.startScreencast", {"format": "jpeg", "quality": quality, "everyNthFrame": 1,
                                                                "maxWidth": self.viewport["width"], "maxHeight": self.viewport["height"]})
                self.touch()
                await asyncio.sleep(0.25)
        finally:
            await stop()

    async def settle(self):
        page = self.page()
        if page:
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=6000)
            except Exception:
                pass
        await asyncio.sleep(0.7)

    async def navigate(self, url: str):
        url = url.strip()
        if not re.match(r"^[a-zA-Z]+:", url):
            if "." in url and " " not in url:
                url = "https://" + url
            else:
                url = "https://www.google.com/search?q=" + quote_plus(url)
        page = await self.ensure_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        if "google." in page.url and "/sorry/" in page.url:
            await self.settle()

    async def new_tab(self, url: str = ""):
        page = await self.ctx.new_page()
        self.adopt(page)
        if self.b.ua:
            await self._apply_ua(page)
        if url:
            await self.navigate(url)

    async def switch_tab(self, index: int):
        ps = self.pages()
        if not 0 <= index < len(ps):
            raise ValueError(f"No tab {index}")
        self.active = index
        self.capture({"kind": "browser", "text": f"Switched to tab {index} ({ps[index].url})"})

    async def close_tab(self, index: int):
        ps = self.pages()
        if not 0 <= index < len(ps):
            raise ValueError(f"No tab {index}")
        await ps[index].close()
        self.active = max(0, min(self.active, len(self.pages()) - 1))
        await self.ensure_page()
        self.capture({"kind": "browser", "text": f"Closed tab {index}"})

    # ---------- dialogs & files ----------
    async def resolve_dialog(self, accept: bool, text: str = ""):
        dlg, self.pending_dialog = self.pending_dialog, None
        if not dlg:
            raise ValueError("No dialog is open")
        try:
            if accept:
                await dlg.accept(text) if (dlg.type == "prompt" and text) else await dlg.accept()
            else:
                await dlg.dismiss()
        except Exception as e:
            raise ValueError(f"The dialog is no longer open ({str(e)[:80]})")
        self.capture({"kind": "browser", "text": f'{"Accepted" if accept else "Dismissed"} dialog "{dlg.message}"' + (f' with "{text}"' if text else "")})

    async def upload(self, file_names: list, element_id=None):
        names = file_names
        paths = [str(await self.files.resolve(n)) for n in names]
        if self.pending_chooser:
            chooser, self.pending_chooser = self.pending_chooser, None
            await chooser.set_files(paths)
        else:
            page = self.page()
            loc = page.locator(f'[data-shadow-id="{element_id}"]') if element_id else page.locator("input[type=file]").first
            await loc.set_input_files(paths, timeout=8000)
        self.capture({"kind": "browser", "text": f"Uploaded file(s): {', '.join(names)}"})

    async def cancel_chooser(self):
        self.pending_chooser = None

    # ---------- agent helpers ----------
    async def elements(self):
        page = self.page()
        try:
            return await asyncio.wait_for(page.evaluate(ELEMENTS_JS), 6)
        except Exception:
            return []

    async def page_text(self, limit=8000):
        page = self.page()
        try:
            t = await asyncio.wait_for(page.inner_text("body"), 8)
        except Exception as e:
            return f"(could not read page: {e})"
        t = re.sub(r"\n\s*\n+", "\n", t)
        return t[:limit]

    # ---------- uniform API (same for cloud and laptop helper) ----------
    async def current_url(self):
        p = self.page()
        return p.url if p else ""

    async def _press(self, page, x, y, count, down):
        await page.mouse.move(x, y)
        n = max(1, min(int(count or 1), 3))
        await (page.mouse.down(click_count=n) if down else page.mouse.up(click_count=n))

    async def input(self, kind, x=None, y=None, text=None, key=None, dy=None, count=None):
        if self.pending_dialog:
            raise ValueError("Answer the page dialog first")
        page = await self.ensure_page()
        acts = {
            "click": lambda: page.mouse.click(x, y),
            "dblclick": lambda: page.mouse.dblclick(x, y),
            "type": lambda: page.keyboard.type(text or ""),
            "key": lambda: page.keyboard.press(key),
            "scroll": lambda: page.mouse.wheel(0, dy or 0),
            "move": lambda: page.mouse.move(x, y),
            "down": lambda: self._press(page, x, y, count, True),
            "up": lambda: self._press(page, x, y, count, False),
        }
        if kind not in acts:
            raise ValueError("Unknown input")
        if kind == "scroll":
            await page.mouse.move(x or 640, y or 400)
        await self.run_guarded(acts[kind](), timeout=15)
        return True

    async def nav(self, action):
        page = await self.ensure_page()
        fn = {"back": page.go_back, "forward": page.go_forward, "reload": page.reload}.get(action)
        if not fn:
            raise ValueError("Unknown action")
        try:
            await fn(timeout=15000)
        except Exception:
            pass
        return True

    async def tabs(self, action, index=None, url=None):
        if action == "new":
            await self.new_tab(url or "https://www.google.com")
        elif action == "switch":
            await self.switch_tab(index)
        elif action == "close":
            await self.close_tab(index)
        else:
            raise ValueError("Unknown action")
        return await self.state()

    async def record_start(self):
        self.recording = []
        page = self.page()
        if page:
            self.capture({"kind": "navigate", "url": page.url})
        return True

    async def record_note(self, text):
        if self.recording is None:
            raise ValueError("Not recording")
        self.capture({"kind": "note", "text": text})
        return True

    async def record_stop(self):
        events, self.recording = self.recording or [], None
        return events

    async def highlight(self, element_id=None, x=None, y=None, label=""):
        page = self.page()
        if not page:
            return False
        try:
            return await asyncio.wait_for(page.evaluate(HIGHLIGHT_JS, [element_id, x, y, label]), 4)
        except Exception:
            return False

    async def unhighlight(self):
        page = self.page()
        if page:
            try:
                await asyncio.wait_for(page.evaluate("() => { const o = document.getElementById('__shadow_hl'); if (o) o.remove(); }"), 4)
            except Exception:
                pass
        return True

    async def corrections_start(self):
        self.correction_sink = []
        return True

    async def corrections_take(self):
        out, self.correction_sink = [e["desc"] for e in (self.correction_sink or [])], None
        return out

    async def take_events(self):
        out, self.events = self.events[-8:], []
        return out

    async def clear_events(self):
        self.events = []
        return True

    async def files_list(self):
        return await self.files.list()

    async def file_read(self, name):
        return await self.files.read(name)

    async def file_write(self, name, content):
        return await self.files.write(name, content)

    async def act(self, name, args):
        if self.pending_dialog and name != "handle_dialog":
            return "ERROR: a dialog is open — call handle_dialog first"
        return await self.run_guarded(self._act(name, args or {}), timeout=90)

    async def _act(self, name, a):
        page = await self.ensure_page()

        def loc():
            return page.locator(f'[data-shadow-id="{a["element_id"]}"]').first
        if name == "navigate":
            await self.navigate(a["url"])
        elif name == "click":
            await loc().click(timeout=6000)
        elif name == "click_at":
            await page.mouse.click(int(a["x"]), int(a["y"]))
        elif name == "type_text":
            await loc().click(timeout=6000)
            if a.get("clear", True):
                await page.keyboard.press("Control+A")
                await page.keyboard.press("Backspace")
            await page.keyboard.type(a["text"], delay=15)
            if a.get("press_enter"):
                await page.keyboard.press("Enter")
        elif name == "select_option":
            try:
                await loc().select_option(label=a["option"], timeout=5000)
            except Exception:
                await loc().select_option(value=a["option"], timeout=5000)
        elif name == "press_key":
            await page.keyboard.press(a["key"])
        elif name == "scroll":
            amt = int(a.get("amount") or 1)
            await page.mouse.wheel(0, (600 if a["direction"] == "down" else -600) * amt)
        elif name == "hover":
            await loc().hover(timeout=5000)
        elif name == "go_back":
            await page.go_back(timeout=15000)
        elif name == "new_tab":
            await self.new_tab(a.get("url", ""))
        elif name == "switch_tab":
            await self.switch_tab(int(a["index"]))
        elif name == "close_tab":
            await self.close_tab(int(a["index"]))
        elif name == "read_page":
            return await self.page_text()
        elif name == "upload_file":
            await self.upload(a["file_names"], a.get("element_id"))
        elif name == "handle_dialog":
            await self.resolve_dialog(bool(a["accept"]), a.get("text", ""))
        else:
            raise ValueError(f"Unknown browser action {name}")
        await self.settle()
        return "ok"


class BrowserSession:
    """One Chrome per user. Workspace "1" (Main) uses the saved profile; every other workspace has its own
    isolated context (own logins, cookies, history) whose storage is saved to disk so it survives restarts."""
    def __init__(self, files, profile_dir: Path, launch: dict = None):
        self.files = files
        self.profile_dir = Path(profile_dir)
        self.state_dir = Path(str(self.profile_dir) + "-ws")
        self.launch = launch or {}
        self.ctx = None
        self.extra = None
        self.groups: dict = {}
        self.owner: dict = {}
        self.closed = False
        self.last_used = time.time()
        self._extra_lock = asyncio.Lock()
        self.ua = None

    def _make_ua(self, ver):
        major = ver.split(".")[0]
        brands = [{"brand": "Chromium", "version": major}, {"brand": "Google Chrome", "version": major}, {"brand": "Not=A?Brand", "version": "24"}]
        self.ua = {"ua": f"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major}.0.0.0 Safari/537.36",
                   "meta": {"brands": brands, "fullVersionList": [{**b, "version": ver if b["brand"] != "Not=A?Brand" else "24.0.0.0"} for b in brands],
                            "fullVersion": ver, "platform": "Linux", "platformVersion": "6.5.0", "architecture": "x86", "model": "", "mobile": False, "bitness": "64"}}

    def touch(self):
        self.last_used = time.time()

    @property
    def recording(self):
        return next((g.recording for g in self.groups.values() if g.recording is not None), None)

    def group(self, gid: str = "1") -> Group:
        g = self.groups.get(str(gid or "1"))
        if not g:
            raise ValueError("This workspace was closed")
        return g

    def _launch_kwargs(self):
        kwargs = {"headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"]}
        kwargs.update(self.launch)
        return kwargs

    def _ctx_kwargs(self):
        kw = {"viewport": VIEWPORT, "accept_downloads": True}
        if self.ua:
            kw.update(user_agent=self.ua["ua"], locale="en-US", extra_http_headers={"Accept-Language": "en-US,en;q=0.9"})
        return kw

    async def start(self):
        pw = await get_playwright()
        prof = self.profile_dir
        prof.mkdir(parents=True, exist_ok=True)
        for f in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
            try:
                os.unlink(prof / f)
            except FileNotFoundError:
                pass
        self.ctx = await pw.chromium.launch_persistent_context(str(prof), **self._ctx_kwargs(), **self._launch_kwargs())
        self.ctx.on("close", self._on_ctx_close)
        try:
            p0 = self.ctx.pages[0] if self.ctx.pages else await self.ctx.new_page()
            native = await p0.evaluate("navigator.userAgent")
            m = re.search(r"HeadlessChrome/([\d.]+)", native)
            if m:
                self._make_ua(m.group(1))
        except Exception as e:
            log.warning("ua detect: %s", e)
        main = self.groups["1"] = Group(self, "1", "Main", self.ctx)
        await main.attach()
        await main.ensure_page()
        if self.ua:
            await asyncio.gather(*[main._apply_ua(p) for p in main.pages()])
        try:
            await main.page().goto("https://www.google.com", wait_until="domcontentloaded", timeout=20000)
        except Exception:
            pass

    def _on_ctx_close(self, *_):
        self.closed = True

    async def _extra_browser(self):
        async with self._extra_lock:
            if self.extra is None or not self.extra.is_connected():
                pw = await get_playwright()
                self.extra = await pw.chromium.launch(**self._launch_kwargs())
            return self.extra

    def _state_path(self, gid):
        return self.state_dir / f"{safe_name(gid)}.json"

    # ---------- workspaces ----------
    async def groups_list(self):
        return [g.info() for g in self.groups.values()]

    async def group_new(self, name="", url="", gid="", label="", urls=None, active=0):
        if gid and gid in self.groups:
            return self.groups[gid].info()
        if len(self.groups) >= MAX_GROUPS:
            raise ValueError(f"You can have up to {MAX_GROUPS} workspaces. Close one first.")
        gid = gid or uuid.uuid4().hex[:8]
        st = self._state_path(gid)
        ctx = await (await self._extra_browser()).new_context(**self._ctx_kwargs(), storage_state=str(st) if st.exists() else None)
        g = Group(self, gid, (name or "").strip()[:40] or f"Workspace {len(self.groups) + 1}", ctx, label)
        self.groups[gid] = g
        await g.attach()
        await g.open_urls(urls or [url or "https://www.google.com"], active)
        return g.info()

    async def group_rename(self, gid, name="", label=None):
        g = self.group(gid)
        g.name = (name or "").strip()[:40] or g.name
        if label is not None:
            g.label = label.strip()[:80]
        return g.info()

    async def group_close(self, gid):
        if str(gid) == "1":
            raise ValueError("The main workspace cannot be closed")
        g = self.group(gid)
        self.groups.pop(g.id, None)
        try:
            await g.ctx.close()
        except Exception:
            pass
        self._state_path(g.id).unlink(missing_ok=True)
        return True

    async def groups_restore(self, groups):
        """Reopen saved workspaces and their tabs (after a restart). Tasks are not resumed here."""
        for snap in groups or []:
            try:
                if snap["id"] == "1":
                    main = self.groups["1"]
                    main.name, main.label = snap.get("name") or "Main", snap.get("label", "")
                    if snap.get("urls"):
                        await main.open_urls(snap["urls"], snap.get("active", 0), reuse_first=True)
                elif len(self.groups) < MAX_GROUPS:
                    await self.group_new(name=snap.get("name", ""), gid=snap["id"], label=snap.get("label", ""),
                                         urls=snap.get("urls"), active=snap.get("active", 0))
            except Exception as e:
                log.warning("restore workspace %s failed: %s", snap.get("id"), e)
        return await self.groups_list()

    async def save_states(self):
        self.state_dir.mkdir(parents=True, exist_ok=True)
        for g in list(self.groups.values()):
            if g.id == "1":
                continue
            try:
                try:
                    await asyncio.wait_for(g.ctx.storage_state(path=str(self._state_path(g.id)), indexed_db=True), 15)
                except TypeError:
                    await asyncio.wait_for(g.ctx.storage_state(path=str(self._state_path(g.id))), 15)
            except Exception as e:
                log.warning("save workspace %s: %s", g.id, e)
        return True

    async def close(self):
        await self.save_states()
        for c in [g.ctx for g in self.groups.values() if g.id != "1"] + [self.ctx]:
            try:
                await c.close()
            except Exception:
                pass
        if self.extra:
            try:
                await self.extra.close()
            except Exception:
                pass
        self.closed = True


async def save_workspaces(db, uid, target, b):
    """Persist workspace names, labels and open tabs (plus their logins on disk) so they survive a restart."""
    try:
        groups = await b.groups_list()
        if getattr(b, "closed", False) or not any(g["tabs"] for g in groups):
            return
        await b.save_states()
    except Exception as e:
        log.warning("save workspaces %s: %s", uid, e)
        return
    await db.workspaces.update_one({"user_id": uid, "target": target},
                                   {"$set": {"groups": groups, "updated_at": now_iso()}}, upsert=True)


async def load_workspaces(db, uid, target):
    doc = await db.workspaces.find_one({"user_id": uid, "target": target}, {"_id": 0})
    return (doc or {}).get("groups") or []


_install_lock = asyncio.Lock()
_install_state = {"ready": False, "error": ""}


async def _run(*cmd, timeout=600):
    p = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    try:
        out, _ = await asyncio.wait_for(p.communicate(), timeout)
    except asyncio.TimeoutError:
        p.kill()
        return 1, "timed out"
    return p.returncode, out.decode(errors="ignore")[-600:]


async def _can_launch():
    pw = await get_playwright()
    try:
        b = await pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        _install_state["version"] = b.version
        await b.close()
        return True, ""
    except Exception as e:
        return False, str(e)[:400]


async def ensure_browser_installed():
    """Make sure a Chromium exists (production images may ship without one); installs it once if missing."""
    if os.environ.get("CHROME_PATH") and Path(os.environ["CHROME_PATH"]).exists():
        _install_state["ready"] = True
        return
    async with _install_lock:
        if _install_state["ready"]:
            return
        if _pw is None and not os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(DATA_DIR / "ms-playwright")
        ok, err = await _can_launch()
        if not ok:
            log.warning("Chromium missing, installing: %s", err[:200])
            code, out = await _run(sys.executable, "-m", "playwright", "install", "chromium")
            ok, err = await _can_launch()
            if not ok:
                code, out = await _run(sys.executable, "-m", "playwright", "install-deps", "chromium")
                log.warning("install-deps exit %s: %s", code, out[-300:])
                ok, err = await _can_launch()
        _install_state.update(ready=ok, error="" if ok else err)
        if not ok:
            log.error("Chromium unavailable: %s", err)


async def get_session(user_id: str, db) -> BrowserSession:
    await ensure_browser_installed()
    if not _install_state["ready"]:
        raise RuntimeError("the browser could not be installed on this server")
    async with _sessions_lock:
        s = _sessions.get(user_id)
        if s and not s.closed:
            return s
        launch = {}
        if os.environ.get("CHROME_PATH") and Path(os.environ["CHROME_PATH"]).exists():
            launch["executable_path"] = os.environ["CHROME_PATH"]
        s = BrowserSession(CloudFiles(user_id, db), user_dir(user_id, "profiles"), launch)
        await s.start()
        await s.groups_restore(await load_workspaces(db, user_id, "cloud"))
        _sessions[user_id] = s
        return s


async def reap_idle(db, active_statuses, idle_secs=1800):
    while True:
        await asyncio.sleep(120)
        for uid, s in list(_sessions.items()):
            if time.time() - s.last_used < idle_secs:
                continue
            if await db.runs.find_one({"user_id": uid, "status": {"$in": active_statuses}}):
                continue
            await save_workspaces(db, uid, "cloud", s)
            _sessions.pop(uid, None)
            try:
                await s.close()
            except Exception:
                pass


async def autosave(db, every=10):
    while True:
        await asyncio.sleep(every)
        for uid, s in list(_sessions.items()):
            if not s.closed:
                await save_workspaces(db, uid, "cloud", s)


async def close_all(db=None):
    for uid, s in list(_sessions.items()):
        try:
            if db is not None:
                await save_workspaces(db, uid, "cloud", s)
            await s.close()
        except Exception:
            pass
    _sessions.clear()
