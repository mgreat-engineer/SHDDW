import asyncio
import base64
import hashlib
import logging

log = logging.getLogger("shadow.hub")


class HelperOffline(Exception):
    pass


class RemoteError(Exception):
    pass


TIMEOUTS = {
    "state": 10, "input": 20, "nav": 20, "navigate": 40, "tabs": 40, "resolve_dialog": 15, "upload": 30,
    "cancel_chooser": 10, "record_start": 10, "record_note": 10, "record_stop": 10, "corrections_start": 10,
    "corrections_take": 10, "take_events": 10, "clear_events": 10, "elements": 15, "page_text": 15,
    "act": 120, "current_url": 10, "files_list": 20, "file_read": 30, "file_write": 30, "highlight": 10, "unhighlight": 10,
    "groups_list": 10, "group_new": 40, "group_rename": 10, "group_close": 20,
    "groups_restore": 180, "save_states": 60,
}


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class HelperConn:
    def __init__(self, ws, device):
        self.ws = ws
        self.device = device
        self.info = {}
        self.pending = {}
        self.n = 0
        self.send_lock = asyncio.Lock()

    async def call(self, method, timeout=60, **params):
        self.n += 1
        fid = self.n
        fut = asyncio.get_running_loop().create_future()
        self.pending[fid] = fut
        try:
            async with self.send_lock:
                await self.ws.send_json({"id": fid, "method": method, "params": params})
            return await asyncio.wait_for(fut, timeout)
        except (RemoteError, HelperOffline):
            raise
        except asyncio.TimeoutError:
            raise RemoteError(f"Laptop did not answer '{method}' in time")
        except Exception as e:
            raise HelperOffline(str(e))
        finally:
            self.pending.pop(fid, None)

    def resolve(self, msg):
        fut = self.pending.get(msg.get("id"))
        if not fut or fut.done():
            return
        if msg.get("error") is not None:
            fut.set_exception(RemoteError(msg["error"]))
        else:
            fut.set_result(msg.get("result"))

    def fail_all(self):
        for fut in self.pending.values():
            if not fut.done():
                fut.set_exception(HelperOffline("Laptop disconnected"))


_conns: dict = {}


def register(user_id, conn):
    old = _conns.get(user_id)
    _conns[user_id] = conn
    return old


def unregister(user_id, conn):
    if _conns.get(user_id) is conn:
        _conns.pop(user_id, None)


def get(user_id):
    return _conns.get(user_id)


class RemoteSession:
    """Same async API as BrowserSession, executed on the user's laptop helper."""

    def __init__(self, conn: HelperConn, gid=None):
        self.conn = conn
        self.gid = gid

    def group(self, gid="1"):
        return RemoteSession(self.conn, str(gid or "1"))

    def _kw(self, kw):
        return {**kw, "group": self.gid} if self.gid and self.gid != "1" else kw

    def touch(self):
        pass

    async def frame(self, quality=60):
        b = await self.conn.call("frame", timeout=12, **self._kw({"quality": quality}))
        return base64.b64decode(b) if b else None

    def __getattr__(self, name):
        if name not in TIMEOUTS:
            raise AttributeError(name)

        async def call(*args, **kw):
            if args:
                raise TypeError(f"{name}() must be called with keyword arguments")
            return await self.conn.call(name, timeout=TIMEOUTS[name], **self._kw(kw))
        return call
