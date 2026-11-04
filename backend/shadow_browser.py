import asyncio
import logging
import time
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


class BrowserSession:
    def __init__(self, files, profile_dir: Path, launch: dict = None):
        self.files = files
        self.profile_dir = Path(profile_dir)
        self.launch = launch or {}
        self.ctx = None
        self.active = 0
        self.recording = None
        self.correction_sink = None
        self.pending_dialog = None
        self.pending_chooser = None
        self.events = []
        self.last_frame = None
        self.closed = False
        self.last_used = time.time()

    def touch(self):
        self.last_used = time.time()

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

    async def start(self):
        pw = await get_playwright()
        prof = self.profile_dir
        prof.mkdir(parents=True, exist_ok=True)
        for f in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
            try:
                os.unlink(prof / f)
            except FileNotFoundError:
                pass
        kwargs = dict(headless=True, viewport=VIEWPORT, accept_downloads=True,
                      args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"])
        kwargs.update(self.launch)
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
        page.on("close", self._on_page_close)

    def _on_page_close(self, _page):
        self.pending_dialog = None
        self.pending_chooser = None

    def _on_page(self, page):
        self._wire(page)
        self.active = len(self.pages()) - 1
        self.push_event(f"Opened new tab {page.url}")

    def _on_nav(self, page, frame):
        if frame == page.main_frame:
            self.pending_dialog = None
            self.pending_chooser = None
        if frame == page.main_frame and frame.url not in ("about:blank", ""):
            self.capture({"kind": "navigate", "url": frame.url})

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

    async def input(self, kind, x=None, y=None, text=None, key=None, dy=None):
        if self.pending_dialog:
            raise ValueError("Answer the page dialog first")
        page = await self.ensure_page()
        acts = {
            "click": lambda: page.mouse.click(x, y),
            "dblclick": lambda: page.mouse.dblclick(x, y),
            "type": lambda: page.keyboard.type(text or ""),
            "key": lambda: page.keyboard.press(key),
            "scroll": lambda: page.mouse.wheel(0, dy or 0),
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


async def get_session(user_id: str, db) -> BrowserSession:
    async with _sessions_lock:
        s = _sessions.get(user_id)
        if s and not s.closed:
            return s
        launch = {}
        if os.environ.get("CHROME_PATH") and Path(os.environ["CHROME_PATH"]).exists():
            launch["executable_path"] = os.environ["CHROME_PATH"]
        s = BrowserSession(CloudFiles(user_id, db), user_dir(user_id, "profiles"), launch)
        await s.start()
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
            _sessions.pop(uid, None)
            try:
                await s.ctx.close()
            except Exception:
                pass


async def close_all():
    for s in list(_sessions.values()):
        try:
            await s.ctx.close()
        except Exception:
            pass
    _sessions.clear()
