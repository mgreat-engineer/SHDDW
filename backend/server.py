import asyncio
import logging
import os
import re
import tempfile
import uuid
from contextlib import suppress
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from pymongo import ASCENDING, DESCENDING, IndexModel
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

try:
    from backend.clerk_auth import clerk_router, require_user
except ModuleNotFoundError:
    from clerk_auth import clerk_router, require_user

import shadow_browser as sb
import shadow_hub as hub
from shadow_hub import HelperOffline, RemoteSession
from shadow_agent import RunEngine, synthesize_skill, llm_key, MODEL

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
log = logging.getLogger("shadow")

INDEXES: dict = {
    "skills": [IndexModel([("user_id", ASCENDING), ("updated_at", DESCENDING)], name="user_updated")],
    "runs": [IndexModel([("id", ASCENDING)], name="id", unique=True),
             IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)], name="user_created")],
    "run_steps": [IndexModel([("run_id", ASCENDING), ("idx", ASCENDING)], name="run_idx")],
    "memories": [IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)], name="user_created")],
    "permissions": [IndexModel([("user_id", ASCENDING), ("category", ASCENDING)], name="user_cat")],
    "files": [IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)], name="user_created")],
    "devices": [IndexModel([("token_hash", ASCENDING)], name="token_hash"), IndexModel([("user_id", ASCENDING)], name="user")],
    "pair_codes": [IndexModel([("code", ASCENDING)], name="code", unique=True)],
    "user_settings": [IndexModel([("user_id", ASCENDING)], name="user", unique=True)],
}


async def ensure_indexes():
    for col, models in INDEXES.items():
        for m in models:
            try:
                await db[col].create_indexes([m])
            except Exception as exc:
                log.error("ensure_indexes(%s): %s", col, exc)


engine = RunEngine(db, None)
app = FastAPI()
api = APIRouter(prefix="/api")
ACTIVE = ["running", "awaiting_approval", "waiting_input", "paused"]


def uid_of(user: dict = Depends(require_user)) -> str:
    return user["user_id"]


def need_key():
    if not llm_key():
        raise HTTPException(400, "Add your OpenAI key first")


async def target_of(uid):
    doc = await db.user_settings.find_one({"user_id": uid}, {"_id": 0})
    return (doc or {}).get("target", "cloud")


async def resolve_session(uid, target):
    if target == "laptop":
        conn = hub.get(uid)
        if not conn:
            raise HelperOffline("Laptop helper is offline")
        return RemoteSession(conn)
    s = await sb.get_session(uid, db)
    s.touch()
    return s


async def session(uid, target=None):
    try:
        return await resolve_session(uid, target or await target_of(uid))
    except HelperOffline:
        raise HTTPException(409, "Your laptop helper is offline. Open Shadow Helper on your laptop, or switch to Cloud.")


async def bcall(coro, code=400):
    """Await a browser call, turning browser/helper errors into clean HTTP errors."""
    try:
        return await coro
    except HTTPException:
        raise
    except HelperOffline:
        raise HTTPException(409, "Your laptop helper went offline.")
    except Exception as e:
        raise HTTPException(code, str(e)[:250])


async def active_run(uid):
    return await db.runs.find_one({"user_id": uid, "status": {"$in": ACTIVE}}, {"_id": 0}, sort=[("created_at", -1)])


@api.get("/status")
async def status(uid: str = Depends(uid_of)):
    return {"openai_configured": bool(llm_key()), "model": MODEL[1]}


# ---------------- browser ----------------
class InputIn(BaseModel):
    kind: str
    x: Optional[float] = None
    y: Optional[float] = None
    text: Optional[str] = None
    key: Optional[str] = None
    dy: Optional[float] = None


class UrlIn(BaseModel):
    url: str


class NavIn(BaseModel):
    action: str


class TabIn(BaseModel):
    action: str
    index: Optional[int] = None
    url: Optional[str] = None


class DialogIn(BaseModel):
    accept: bool
    text: Optional[str] = ""


class ChooserIn(BaseModel):
    file_names: List[str] = []
    cancel: bool = False


async def take_over(uid, s):
    run = await active_run(uid)
    if run and run["status"] == "running":
        await db.runs.update_one({"id": run["id"]}, {"$set": {"status": "paused", "paused_by": "takeover"}})
        await s.corrections_start()


@api.get("/browser/state")
async def browser_state(uid: str = Depends(uid_of)):
    s = await session(uid)
    st = await bcall(s.state(), 503)
    st["target"] = await target_of(uid)
    return st


@api.get("/browser/frame")
async def browser_frame(uid: str = Depends(uid_of)):
    s = await session(uid)
    data = await bcall(s.frame(), 503)
    if not data:
        raise HTTPException(503, "No frame yet")
    return Response(content=data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@api.post("/browser/input")
async def browser_input(body: InputIn, uid: str = Depends(uid_of)):
    s = await session(uid)
    await take_over(uid, s)
    await bcall(s.input(kind=body.kind, x=body.x, y=body.y, text=body.text, key=body.key, dy=body.dy), 409)
    return {"ok": True}


@api.post("/browser/navigate")
async def browser_navigate(body: UrlIn, uid: str = Depends(uid_of)):
    s = await session(uid)
    await take_over(uid, s)
    await bcall(s.navigate(url=body.url))
    return {"ok": True}


@api.post("/browser/nav")
async def browser_nav(body: NavIn, uid: str = Depends(uid_of)):
    s = await session(uid)
    await bcall(s.nav(action=body.action))
    return {"ok": True}


@api.post("/browser/tabs")
async def browser_tabs(body: TabIn, uid: str = Depends(uid_of)):
    s = await session(uid)
    return await bcall(s.tabs(action=body.action, index=body.index, url=body.url))


@api.post("/browser/dialog")
async def browser_dialog(body: DialogIn, uid: str = Depends(uid_of)):
    s = await session(uid)
    await bcall(s.resolve_dialog(accept=body.accept, text=body.text or ""))
    return {"ok": True}


@api.post("/browser/filechooser")
async def browser_chooser(body: ChooserIn, uid: str = Depends(uid_of)):
    s = await session(uid)
    if body.cancel:
        await bcall(s.cancel_chooser())
    else:
        await bcall(s.upload(file_names=body.file_names))
    return {"ok": True}


@api.get("/target/files")
async def target_files(uid: str = Depends(uid_of)):
    s = await session(uid)
    return await bcall(s.files_list())


# ---------------- recording ----------------
class NoteIn(BaseModel):
    text: str


@api.post("/record/start")
async def record_start(uid: str = Depends(uid_of)):
    run = await active_run(uid)
    if run and run["status"] == "running":
        raise HTTPException(409, "Shadow is running a task. Pause or stop it first.")
    s = await session(uid)
    await bcall(s.record_start())
    return {"ok": True}


@api.post("/record/note")
async def record_note(body: NoteIn, uid: str = Depends(uid_of)):
    s = await session(uid)
    await bcall(s.record_note(text=body.text))
    return {"ok": True}


@api.post("/record/stop")
async def record_stop(uid: str = Depends(uid_of)):
    s = await session(uid)
    return {"events": await bcall(s.record_stop())}


class SynthIn(BaseModel):
    events: list
    hint: Optional[str] = ""


@api.post("/skills/synthesize")
async def skills_synth(body: SynthIn, uid: str = Depends(uid_of)):
    need_key()
    if not body.events:
        raise HTTPException(400, "Nothing was recorded")
    try:
        return await synthesize_skill(body.events, body.hint or "")
    except Exception as e:
        raise HTTPException(502, f"AI could not build the skill: {str(e)[:200]}")


# ---------------- skills ----------------
class SkillIn(BaseModel):
    name: str
    description: Optional[str] = ""
    steps: List[str] = []
    parameters: list = []
    events: list = []


@api.get("/skills")
async def skills_list(uid: str = Depends(uid_of)):
    return await db.skills.find({"user_id": uid}, {"_id": 0, "events": 0}).sort("updated_at", -1).to_list(500)


@api.post("/skills")
async def skills_create(body: SkillIn, uid: str = Depends(uid_of)):
    now = sb.now_iso()
    doc = {"id": str(uuid.uuid4()), "user_id": uid, **body.model_dump(), "history": [], "created_at": now, "updated_at": now}
    await db.skills.insert_one(doc)
    doc.pop("_id", None)
    doc.pop("events", None)
    return doc


@api.put("/skills/{sid}")
async def skills_update(sid: str, body: SkillIn, uid: str = Depends(uid_of)):
    data = body.model_dump(exclude={"events"})
    r = await db.skills.update_one({"id": sid, "user_id": uid}, {"$set": {**data, "updated_at": sb.now_iso()}})
    if not r.matched_count:
        raise HTTPException(404, "Not found")
    return await db.skills.find_one({"id": sid, "user_id": uid}, {"_id": 0, "events": 0})


@api.delete("/skills/{sid}")
async def skills_delete(sid: str, uid: str = Depends(uid_of)):
    r = await db.skills.delete_one({"id": sid, "user_id": uid})
    if not r.deleted_count:
        raise HTTPException(404, "Not found")
    await db.permissions.delete_many({"user_id": uid, "skill_id": sid})
    return {"ok": True}


# ---------------- runs ----------------
class RunIn(BaseModel):
    command: Optional[str] = ""
    skill_id: Optional[str] = None


class ApprovalIn(BaseModel):
    decision: str  # approve | reject | always | always_skill


class ReplyIn(BaseModel):
    text: str


async def get_run(rid, uid):
    run = await db.runs.find_one({"id": rid, "user_id": uid}, {"_id": 0})
    if not run:
        raise HTTPException(404, "Not found")
    return run


@api.post("/runs")
async def runs_create(body: RunIn, uid: str = Depends(uid_of)):
    need_key()
    cur = await active_run(uid)
    if cur:
        if cur["status"] == "waiting_input" and body.command:
            return await runs_reply(cur["id"], ReplyIn(text=body.command), uid)
        raise HTTPException(409, "A task is already in progress. Finish, stop or resume it first.")
    target = await target_of(uid)
    s = await session(uid, target)
    if (await bcall(s.state(), 409)).get("recording"):
        raise HTTPException(409, "Stop recording first")
    skill = None
    if body.skill_id:
        skill = await db.skills.find_one({"id": body.skill_id, "user_id": uid}, {"_id": 0})
        if not skill:
            raise HTTPException(404, "Skill not found")
    goal = (body.command or "").strip() or (f'Run skill "{skill["name"]}"' if skill else "")
    if not goal:
        raise HTTPException(400, "Tell Shadow what to do")
    now = sb.now_iso()
    run = {"id": str(uuid.uuid4()), "user_id": uid, "goal": goal, "skill_id": skill["id"] if skill else None,
           "skill_name": skill["name"] if skill else None, "loaded_skills": [skill["id"]] if skill else [],
           "status": "running", "plan": [], "scratch": {}, "messages": [], "corrections": [], "pending": None,
           "step_count": 0, "summary": "", "target": target, "created_at": now, "updated_at": now}
    await db.runs.insert_one(run)
    run.pop("_id", None)
    await bcall(s.clear_events())
    engine.start(run["id"], uid)
    return run


@api.get("/runs")
async def runs_list(uid: str = Depends(uid_of)):
    return await db.runs.find({"user_id": uid}, {"_id": 0, "scratch": 0}).sort("created_at", -1).to_list(100)


@api.get("/runs/active")
async def runs_active(uid: str = Depends(uid_of)):
    return {"run": await active_run(uid)}


@api.get("/runs/{rid}")
async def runs_get(rid: str, uid: str = Depends(uid_of)):
    run = await get_run(rid, uid)
    run["steps"] = await db.run_steps.find({"run_id": rid}, {"_id": 0}).sort("idx", -1).to_list(200)
    return run


@api.get("/runs/{rid}/shot/{idx}")
async def runs_shot(rid: str, idx: int, uid: str = Depends(uid_of)):
    await get_run(rid, uid)
    p = sb.user_dir(uid, f"shots/{rid}") / f"{idx}.jpg"
    if not p.exists():
        raise HTTPException(404, "No screenshot")
    return FileResponse(p, media_type="image/jpeg")


@api.post("/runs/{rid}/approval")
async def runs_approval(rid: str, body: ApprovalIn, uid: str = Depends(uid_of)):
    run = await get_run(rid, uid)
    if run["status"] != "awaiting_approval" or not run.get("pending"):
        raise HTTPException(400, "Nothing to approve")
    pend = run["pending"]
    if body.decision == "reject":
        msg = (f'User REFUSED the outcome of {pend["tool"]}({pend["args"]}) (risk: {pend["risk"]}). Do NOT achieve this outcome by any other '
               f'means (no other button, key, URL or form). Any further "{pend["risk"]}" action is blocked for this run. Continue only with parts '
               f'of the goal that do not need it, otherwise finish or ask_user.')
        await db.runs.update_one({"id": rid}, {"$set": {"status": "running", "pending": None},
                                               "$push": {"messages": msg}, "$addToSet": {"blocked_risks": pend["risk"]}})
    else:
        if body.decision in ("always", "always_skill"):
            skill_id = run.get("skill_id") if body.decision == "always_skill" else None
            await db.permissions.update_one({"user_id": uid, "category": pend["risk"], "skill_id": skill_id},
                {"$setOnInsert": {"id": str(uuid.uuid4()), "created_at": sb.now_iso(), "source": "approval",
                                  "skill_name": run.get("skill_name") if skill_id else None}}, upsert=True)
        await db.runs.update_one({"id": rid}, {"$set": {"status": "running", "pending": {**pend, "approved": True}}})
    engine.start(rid, uid)
    return {"ok": True}


@api.post("/runs/{rid}/reply")
async def runs_reply(rid: str, body: ReplyIn, uid: str = Depends(uid_of)):
    run = await get_run(rid, uid)
    if run["status"] not in ("waiting_input", "running", "paused"):
        raise HTTPException(400, "This task is not active")
    q = (run.get("pending") or {}).get("question")
    msg = f'Shadow asked: "{q}" — user replied: {body.text}' if q else body.text
    upd = {"$push": {"messages": msg}}
    if run["status"] == "waiting_input":
        upd["$set"] = {"status": "running", "pending": None}
    await db.runs.update_one({"id": rid}, upd)
    if run["status"] == "waiting_input":
        engine.start(rid, uid)
    return await get_run(rid, uid)


@api.post("/runs/{rid}/pause")
async def runs_pause(rid: str, uid: str = Depends(uid_of)):
    run = await get_run(rid, uid)
    if run["status"] != "running":
        raise HTTPException(400, "Not running")
    await db.runs.update_one({"id": rid}, {"$set": {"status": "paused"}})
    s = await session(uid, run.get("target", "cloud"))
    await bcall(s.corrections_start())
    return {"ok": True}


@api.post("/runs/{rid}/resume")
async def runs_resume(rid: str, uid: str = Depends(uid_of)):
    need_key()
    run = await get_run(rid, uid)
    if run["status"] not in ("paused", "failed", "stopped"):
        raise HTTPException(400, "Cannot resume")
    s = await session(uid, run.get("target", "cloud"))
    corr = await bcall(s.corrections_take())
    await bcall(s.clear_events())
    upd = {"$set": {"status": "running", "pending": None, "summary": ""}}
    if corr:
        upd["$push"] = {"corrections": {"$each": corr[-60:]}}
    await db.runs.update_one({"id": rid}, upd)
    engine.start(rid, uid)
    return {"ok": True, "corrections": len(corr)}


@api.post("/runs/{rid}/stop")
async def runs_stop(rid: str, uid: str = Depends(uid_of)):
    run = await get_run(rid, uid)
    if run["status"] not in ACTIVE:
        raise HTTPException(400, "Not active")
    await db.runs.update_one({"id": rid}, {"$set": {"status": "stopped", "pending": None, "summary": run.get("summary") or "Stopped by you."}})
    with suppress(Exception):
        s = await resolve_session(uid, run.get("target", "cloud"))
        await s.corrections_take()
    return {"ok": True}


# ---------------- memory ----------------
class MemoryIn(BaseModel):
    content: str


@api.get("/memories")
async def mem_list(uid: str = Depends(uid_of)):
    return await db.memories.find({"user_id": uid}, {"_id": 0}).sort("created_at", -1).to_list(500)


@api.post("/memories")
async def mem_create(body: MemoryIn, uid: str = Depends(uid_of)):
    if not body.content.strip():
        raise HTTPException(400, "Empty")
    doc = {"id": str(uuid.uuid4()), "user_id": uid, "content": body.content.strip(), "source": "user", "created_at": sb.now_iso()}
    await db.memories.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.put("/memories/{mid}")
async def mem_update(mid: str, body: MemoryIn, uid: str = Depends(uid_of)):
    r = await db.memories.update_one({"id": mid, "user_id": uid}, {"$set": {"content": body.content.strip()}})
    if not r.matched_count:
        raise HTTPException(404, "Not found")
    return {"ok": True}


@api.delete("/memories/{mid}")
async def mem_delete(mid: str, uid: str = Depends(uid_of)):
    r = await db.memories.delete_one({"id": mid, "user_id": uid})
    if not r.deleted_count:
        raise HTTPException(404, "Not found")
    return {"ok": True}


# ---------------- permissions ----------------
class PermIn(BaseModel):
    category: str
    skill_id: Optional[str] = None


@api.get("/permissions")
async def perm_list(uid: str = Depends(uid_of)):
    return await db.permissions.find({"user_id": uid}, {"_id": 0}).sort("created_at", -1).to_list(100)


@api.post("/permissions")
async def perm_create(body: PermIn, uid: str = Depends(uid_of)):
    if body.category not in ("pay", "send", "delete"):
        raise HTTPException(400, "Unknown category")
    skill_name = None
    if body.skill_id:
        sk = await db.skills.find_one({"id": body.skill_id, "user_id": uid})
        if not sk:
            raise HTTPException(404, "Skill not found")
        skill_name = sk["name"]
    await db.permissions.update_one({"user_id": uid, "category": body.category, "skill_id": body.skill_id},
        {"$setOnInsert": {"id": str(uuid.uuid4()), "created_at": sb.now_iso(), "source": "settings", "skill_name": skill_name}}, upsert=True)
    return await perm_list(uid)


@api.delete("/permissions/{pid}")
async def perm_delete(pid: str, uid: str = Depends(uid_of)):
    r = await db.permissions.delete_one({"id": pid, "user_id": uid})
    if not r.deleted_count:
        raise HTTPException(404, "Not found")
    return {"ok": True}


# ---------------- files ----------------
@api.get("/files")
async def files_list(uid: str = Depends(uid_of)):
    return await db.files.find({"user_id": uid}, {"_id": 0}).sort("created_at", -1).to_list(500)


@api.post("/files")
async def files_upload(file: UploadFile = File(...), uid: str = Depends(uid_of)):
    d = sb.user_dir(uid, "files")
    name = sb.safe_name(file.filename)
    data = await file.read()
    if len(data) > 100 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 100 MB)")
    (d / name).write_bytes(data)
    await db.files.update_one({"user_id": uid, "name": name}, {"$set": {"size": len(data), "source": "upload", "created_at": sb.now_iso()},
                              "$setOnInsert": {"id": str(uuid.uuid4())}}, upsert=True)
    return await db.files.find_one({"user_id": uid, "name": name}, {"_id": 0})


async def get_file(fid, uid):
    f = await db.files.find_one({"id": fid, "user_id": uid}, {"_id": 0})
    if not f:
        raise HTTPException(404, "Not found")
    return f, sb.user_dir(uid, "files") / f["name"]


@api.get("/files/{fid}/download")
async def files_download(fid: str, uid: str = Depends(uid_of)):
    f, p = await get_file(fid, uid)
    if not p.exists():
        raise HTTPException(404, "File missing")
    return FileResponse(p, filename=f["name"])


@api.delete("/files/{fid}")
async def files_delete(fid: str, uid: str = Depends(uid_of)):
    f, p = await get_file(fid, uid)
    with suppress(FileNotFoundError):
        p.unlink()
    await db.files.delete_one({"id": fid, "user_id": uid})
    return {"ok": True}


# ---------------- voice ----------------
@api.post("/voice/transcribe")
async def voice(file: UploadFile = File(...), uid: str = Depends(uid_of)):
    need_key()
    from emergentintegrations.llm.openai import OpenAISpeechToText
    suffix = Path(file.filename or "a.webm").suffix or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        path = tmp.name
    try:
        stt = OpenAISpeechToText(api_key=llm_key())
        with open(path, "rb") as fh:
            res = await stt.transcribe(file=fh, model="whisper-1", response_format="json")
        return {"text": getattr(res, "text", "") or (res.get("text", "") if isinstance(res, dict) else str(res))}
    except Exception as e:
        raise HTTPException(502, f"Could not transcribe: {str(e)[:200]}")
    finally:
        os.unlink(path)


# ---------------- laptop helper (desktop app) ----------------
class TargetIn(BaseModel):
    target: str


class PairIn(BaseModel):
    code: str
    name: Optional[str] = "My laptop"


def _device_out(d):
    conn = hub.get(d["user_id"])
    online = bool(conn and conn.device["id"] == d["id"])
    return {"id": d["id"], "name": d.get("name"), "created_at": d.get("created_at"), "last_seen": d.get("last_seen"),
            "online": online, "info": (conn.info if online else d.get("info")) or {}}


@api.get("/target")
async def target_get(uid: str = Depends(uid_of)):
    conn = hub.get(uid)
    return {"target": await target_of(uid), "helper_online": bool(conn),
            "helper": {"name": conn.device.get("name"), "info": conn.info} if conn else None}


@api.put("/target")
async def target_put(body: TargetIn, uid: str = Depends(uid_of)):
    if body.target not in ("cloud", "laptop"):
        raise HTTPException(400, "Unknown target")
    if body.target == "laptop" and not hub.get(uid):
        raise HTTPException(409, "Your laptop helper is offline.")
    if await active_run(uid):
        raise HTTPException(409, "Finish or stop the current task before switching.")
    await db.user_settings.update_one({"user_id": uid}, {"$set": {"target": body.target}}, upsert=True)
    return await target_get(uid)


@api.post("/devices/pair-code")
async def devices_pair_code(uid: str = Depends(uid_of)):
    import secrets
    from pymongo.errors import DuplicateKeyError
    exp = datetime.now(timezone.utc) + timedelta(minutes=15)
    for _ in range(5):
        code = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(8))
        try:
            await db.pair_codes.insert_one({"code": code, "user_id": uid, "expires_at": exp.isoformat()})
            break
        except DuplicateKeyError:
            continue
    return {"code": code, "expires_at": exp.isoformat()}


@api.get("/devices")
async def devices_list(uid: str = Depends(uid_of)):
    docs = await db.devices.find({"user_id": uid, "revoked": {"$ne": True}}, {"_id": 0, "token_hash": 0}).sort("created_at", -1).to_list(20)
    return [_device_out(d) for d in docs]


@api.delete("/devices/{did}")
async def devices_revoke(did: str, uid: str = Depends(uid_of)):
    r = await db.devices.update_one({"id": did, "user_id": uid}, {"$set": {"revoked": True}})
    if not r.matched_count:
        raise HTTPException(404, "Not found")
    conn = hub.get(uid)
    if conn and conn.device["id"] == did:
        with suppress(Exception):
            await conn.ws.close(code=4401)
        hub.unregister(uid, conn)
        await db.user_settings.update_one({"user_id": uid}, {"$set": {"target": "cloud"}}, upsert=True)
    elif not hub.get(uid):
        await db.user_settings.update_one({"user_id": uid}, {"$set": {"target": "cloud"}}, upsert=True)
    return {"ok": True}


@api.post("/helper/pair")
async def helper_pair(body: PairIn):
    import secrets
    pc = await db.pair_codes.find_one_and_delete({"code": body.code.strip().upper()})
    if not pc or pc["expires_at"] < sb.now_iso():
        raise HTTPException(400, "This connection code is wrong or expired. Get a new one in Shadow.")
    token = secrets.token_urlsafe(32)
    dev = {"id": str(uuid.uuid4()), "user_id": pc["user_id"], "name": (body.name or "My laptop")[:60],
           "token_hash": hub.hash_token(token), "created_at": sb.now_iso(), "last_seen": sb.now_iso()}
    await db.devices.insert_one(dev)
    return {"token": token, "device_id": dev["id"], "name": dev["name"]}


@app.websocket("/api/helper/ws")
async def helper_ws(ws: WebSocket):
    auth = ws.headers.get("authorization", "")
    token = auth[7:] if auth.lower().startswith("bearer ") else ""
    dev = await db.devices.find_one({"token_hash": hub.hash_token(token), "revoked": {"$ne": True}}, {"_id": 0}) if token else None
    if not dev:
        await ws.close(code=4401)
        return
    await ws.accept()
    uid = dev["user_id"]
    conn = hub.HelperConn(ws, dev)
    old = hub.register(uid, conn)
    if old:
        old.fail_all()
        with suppress(Exception):
            await old.ws.close(code=4000)
    first = not await db.user_settings.find_one({"user_id": uid})
    if first and not await active_run(uid):
        await db.user_settings.update_one({"user_id": uid}, {"$set": {"target": "laptop"}}, upsert=True)
    await db.devices.update_one({"id": dev["id"]}, {"$set": {"last_seen": sb.now_iso()}})
    try:
        while True:
            msg = await ws.receive_json()
            if "id" in msg:
                conn.resolve(msg)
            elif msg.get("event") == "hello":
                conn.info = msg.get("info") or {}
                await db.devices.update_one({"id": dev["id"]}, {"$set": {"info": conn.info, "last_seen": sb.now_iso()}})
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        hub.unregister(uid, conn)
        conn.fail_all()
        await db.devices.update_one({"id": dev["id"]}, {"$set": {"last_seen": sb.now_iso()}})


engine.resolver = resolve_session
app.include_router(api)
app.include_router(clerk_router)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


@app.on_event("startup")
async def startup():
    app.state.index_task = asyncio.create_task(ensure_indexes())
    app.state.reaper = asyncio.create_task(sb.reap_idle(db, ACTIVE))
    await db.runs.update_many({"status": "running"}, {"$set": {"status": "paused", "summary": "Interrupted by a restart — press Resume to continue from the last step."}})


@app.on_event("shutdown")
async def shutdown():
    app.state.index_task.cancel()
    with suppress(asyncio.CancelledError):
        await app.state.index_task
    await sb.close_all()
    client.close()
