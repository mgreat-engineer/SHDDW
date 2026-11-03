import asyncio
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

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


class BrowserSession:
    def __init__(self, user_id: str, db):
        self.user_id = user_id
        self.db = db
        self.ctx = None
        self.active = 0
        self.recording = None
        self.correction_sink = None
        self.pending_dialog = None
        self.pending_chooser = None
        self.events = []
        self.last_frame = None
        self.closed = False

    async def start(self):
        pw = await get_playwright()
        prof = user_dir(self.user_id, "profiles")
        for f in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
            try:
                os.unlink(prof / f)
            except FileNotFoundError:
                pass
        kwargs = dict(headless=True, viewport=VIEWPORT, accept_downloads=True,
                      args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"])
        if os.environ.get("CHROME_PATH") and Path(os.environ["CHROME_PATH"]).exists():
            kwargs["executable_path"] = os.environ["CHROME_PATH"]
        self.ctx = await pw.chromium.launch_persistent_context(str(prof), **kwargs)
        await self.ctx.expose_binding("__shadowRecord", self._on_record)
        await self.ctx.add_init_script(RECORDER_JS)
        self.ctx.on("page", self._on_page)
        self.ctx.on("close", self._on_ctx_close)
        for p in self.ctx.pages:
            self._wire(p)
        if not self.ctx.pages:
            await self.ctx.new_page()
        try:
            await self.page().goto("https://www.google.com", wait_until="domcontentloaded", timeout=20000)
        except Exception:
            pass

    def _on_ctx_close(self, *_):
        self.closed = True

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

    async def _on_record(self, source, payload):
        import json
        try:
            ev = json.loads(payload)
        except Exception:
            return
        self.capture(ev)

    def _wire(self, page):
        page.on("dialog", self._on_dialog)
        page.on("download", self._on_download)
        page.on("filechooser", self._on_chooser)
        page.on("framenavigated", lambda fr, p=page: self._on_nav(p, fr))

    def _on_page(self, page):
        self._wire(page)
        self.active = len(self.pages()) - 1
        self.push_event(f"Opened new tab {page.url}")

    def _on_nav(self, page, frame):
        if frame == page.main_frame and frame.url not in ("about:blank", ""):
            self.capture({"kind": "navigate", "url": frame.url})

    async def _on_dialog(self, dialog):
        self.pending_dialog = dialog
        self.push_event(f'Dialog appeared ({dialog.type}): "{dialog.message}"')

    def _on_chooser(self, chooser):
        self.pending_chooser = chooser
        self.push_event("File picker opened (waiting for a file to be chosen)")

    async def _on_download(self, download):
        d = user_dir(self.user_id, "files")
        name = safe_name(download.suggested_filename)
        target = d / name
        if target.exists():
            target = d / f"{Path(name).stem}-{uuid.uuid4().hex[:5]}{Path(name).suffix}"
        try:
            await download.save_as(str(target))
        except Exception as e:
            self.push_event(f"Download failed: {e}")
            return
        await self.db.files.insert_one({
            "id": str(uuid.uuid4()), "user_id": self.user_id, "name": target.name,
            "size": target.stat().st_size, "source": "download", "created_at": now_iso()})
        self.push_event(f"Downloaded file {target.name}")

    # ---------- tabs ----------
    def pages(self):
        return [p for p in self.ctx.pages if not p.is_closed()]

    def page(self):
        ps = self.pages()
        if not ps:
            return None
        self.active = max(0, min(self.active, len(ps) - 1))
        return ps[self.active]

    async def ensure_page(self):
        if not self.pages():
            await self.ctx.new_page()
            self.active = 0
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
        return {
            "tabs": tabs,
            "recording": self.recording is not None,
            "recorded": [e["desc"] for e in (self.recording or [])][-8:],
            "recorded_count": len(self.recording or []),
            "dialog": {"type": dlg.type, "message": dlg.message, "default": dlg.default_value} if dlg else None,
            "file_chooser": bool(self.pending_chooser),
            "viewport": VIEWPORT,
        }

    async def frame(self, quality=60):
        page = await self.ensure_page()
        try:
            self.last_frame = await page.screenshot(type="jpeg", quality=quality, timeout=4000)
        except Exception:
            pass
        return self.last_frame

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
            url = ("https://" + url) if ("." in url and " " not in url) else "https://www.google.com/search?q=" + url
        page = await self.ensure_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)

    async def new_tab(self, url: str = ""):
        page = await self.ctx.new_page()
        self.active = self.pages().index(page)
        if url:
            await self.navigate(url)

    async def switch_tab(self, index: int):
        ps = self.pages()
        if not 0 <= index < len(ps):
            raise ValueError(f"No tab {index}")
        self.active = index
        await ps[index].bring_to_front()
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
        if accept:
            await dlg.accept(text) if (dlg.type == "prompt" and text) else await dlg.accept()
        else:
            await dlg.dismiss()
        self.capture({"kind": "browser", "text": f'{"Accepted" if accept else "Dismissed"} dialog "{dlg.message}"' + (f' with "{text}"' if text else "")})

    async def upload(self, names: list, element_id=None):
        d = user_dir(self.user_id, "files")
        paths = []
        for n in names:
            p = d / safe_name(n)
            if not p.exists():
                raise ValueError(f"File not found in Files: {n}")
            paths.append(str(p))
        if self.pending_chooser:
            chooser, self.pending_chooser = self.pending_chooser, None
            await chooser.set_files(paths)
        else:
            page = self.page()
            loc = page.locator(f'[data-shadow-id="{element_id}"]') if element_id else page.locator("input[type=file]").first
            await loc.set_input_files(paths, timeout=8000)
        self.capture({"kind": "browser", "text": f"Uploaded file(s): {', '.join(names)}"})

    def cancel_chooser(self):
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


async def get_session(user_id: str, db) -> BrowserSession:
    async with _sessions_lock:
        s = _sessions.get(user_id)
        if s and not s.closed:
            return s
        s = BrowserSession(user_id, db)
        await s.start()
        _sessions[user_id] = s
        return s


async def close_all():
    for s in list(_sessions.values()):
        try:
            await s.ctx.close()
        except Exception:
            pass
    _sessions.clear()
