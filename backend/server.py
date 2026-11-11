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
from fastapi import APIRouter, Depends, FastAPI, File, HTTPException, Query, Request, UploadFile, WebSocket, WebSocketDisconnect
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
import shadow_schedule as sched


def sched_version(v):
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:3]) or (0,)
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
    "workspaces": [IndexModel([("user_id", ASCENDING), ("target", ASCENDING)], name="user_target", unique=True)],
    "schedules": [IndexModel([("user_id", ASCENDING)], name="user"), IndexModel([("enabled", ASCENDING), ("next_run_at", ASCENDING)], name="due")],
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


def gid_of(group: str = Query("1", pattern=r"^[a-z0-9]{1,12}$")) -> str:
    return group


def need_key():
    if not llm_key():
        raise HTTPException(400, "Add your OpenAI key first")


async def target_of(uid):
    doc = await db.user_settings.find_one({"user_id": uid}, {"_id": 0})
    return (doc or {}).get("target", "cloud")


async def resolve_browser(uid, target):
    if target == "laptop":
        conn = hub.get(uid)
        if not conn:
            raise HelperOffline("Laptop helper is offline")
        return RemoteSession(conn)
    s = await sb.get_session(uid, db)
    s.touch()
    return s


async def resolve_session(uid, target, gid="1"):
    return (await resolve_browser(uid, target)).group(gid)


async def session(uid, target=None, gid="1", whole=False):
    try:
        b = await resolve_browser(uid, target or await target_of(uid))
        return b if whole else b.group(gid)
    except HelperOffline:
        raise HTTPException(409, "Your laptop helper is offline. Open Shadow Helper on your laptop, or switch to Cloud.")
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        log.exception("cloud browser failed to start")
        raise HTTPException(503, f"Shadow's cloud browser could not start: {str(e)[:160]}")


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


async def active_run(uid, gid=None):
    q = {"user_id": uid, "status": {"$in": ACTIVE}}
    if gid:
        q["group_id"] = gid
    return await db.runs.find_one(q, {"_id": 0}, sort=[("created_at", -1)])


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


async def take_over(uid, s, gid):
    run = await active_run(uid, gid)
    if run and run["status"] == "running":
        await db.runs.update_one({"id": run["id"]}, {"$set": {"status": "paused", "paused_by": "takeover"}})
        await s.corrections_start()


@api.get("/browser/state")
async def browser_state(uid: str = Depends(uid_of), gid: str = Depends(gid_of)):
    s = await session(uid, gid=gid)
    st = await bcall(s.state(), 503)
    st["target"] = await target_of(uid)
    return st


@api.get("/browser/frame")
async def browser_frame(uid: str = Depends(uid_of), gid: str = Depends(gid_of), quality: int = Query(60, ge=20, le=80)):
    s = await session(uid, gid=gid)
    data = await bcall(s.frame(quality=quality), 503)
    if not data:
        raise HTTPException(503, "No frame yet")
    return Response(content=data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@api.post("/browser/input")
async def browser_input(body: InputIn, uid: str = Depends(uid_of), gid: str = Depends(gid_of)):
    s = await session(uid, gid=gid)
    await take_over(uid, s, gid)
    await bcall(s.input(kind=body.kind, x=body.x, y=body.y, text=body.text, key=body.key, dy=body.dy), 409)
    return {"ok": True}


@api.post("/browser/navigate")
async def browser_navigate(body: UrlIn, uid: str = Depends(uid_of), gid: str = Depends(gid_of)):
    s = await session(uid, gid=gid)
    await take_over(uid, s, gid)
    await bcall(s.navigate(url=body.url))
    asyncio.create_task(persist(uid, await session(uid, whole=True)))
    return {"ok": True}


@api.post("/browser/nav")
async def browser_nav(body: NavIn, uid: str = Depends(uid_of), gid: str = Depends(gid_of)):
    s = await session(uid, gid=gid)
    await bcall(s.nav(action=body.action))
    return {"ok": True}


@api.post("/browser/tabs")
async def browser_tabs(body: TabIn, uid: str = Depends(uid_of), gid: str = Depends(gid_of)):
    s = await session(uid, gid=gid)
    out = await bcall(s.tabs(action=body.action, index=body.index, url=body.url))
    asyncio.create_task(persist(uid, await session(uid, whole=True)))
    return out


@api.post("/browser/dialog")
async def browser_dialog(body: DialogIn, uid: str = Depends(uid_of), gid: str = Depends(gid_of)):
    s = await session(uid, gid=gid)
    await bcall(s.resolve_dialog(accept=body.accept, text=body.text or ""))
    return {"ok": True}


@api.post("/browser/filechooser")
async def browser_chooser(body: ChooserIn, uid: str = Depends(uid_of), gid: str = Depends(gid_of)):
    s = await session(uid, gid=gid)
    if body.cancel:
        await bcall(s.cancel_chooser())
    else:
        await bcall(s.upload(file_names=body.file_names))
    return {"ok": True}


@api.get("/target/files")
async def target_files(uid: str = Depends(uid_of)):
    s = await session(uid)
    return await bcall(s.files_list())


# ---------------- workspaces ----------------
class GroupIn(BaseModel):
    name: Optional[str] = ""
    url: Optional[str] = ""
    label: Optional[str] = None


async def persist(uid, b, target=None):
    await sb.save_workspaces(db, uid, target or await target_of(uid), b)


@api.get("/browser/groups")
async def groups_list(uid: str = Depends(uid_of)):
    b = await session(uid, whole=True)
    groups = await bcall(b.groups_list(), 503)
    runs = await db.runs.find({"user_id": uid, "status": {"$in": ACTIVE}}, {"_id": 0, "id": 1, "status": 1, "goal": 1, "group_id": 1}).to_list(50)
    by = {r.get("group_id", "1"): r for r in runs}
    return {"groups": [{**g, "run": by.get(g["id"])} for g in groups], "max": sb.MAX_GROUPS}


@api.post("/browser/groups")
async def groups_create(body: GroupIn, uid: str = Depends(uid_of)):
    b = await session(uid, whole=True)
    g = await bcall(b.group_new(name=body.name or "", url=body.url or "", label=body.label or ""), 409)
    await persist(uid, b)
    return g


@api.put("/browser/groups/{gid}")
async def groups_rename(gid: str, body: GroupIn, uid: str = Depends(uid_of)):
    b = await session(uid, whole=True)
    g = await bcall(b.group_rename(gid=gid, name=body.name or "", label=body.label), 404)
    await persist(uid, b)
    return g


@api.delete("/browser/groups/{gid}")
async def groups_close(gid: str, uid: str = Depends(uid_of)):
    if await active_run(uid, gid):
        raise HTTPException(409, "Shadow is working in this workspace. Stop its task first.")
    if gid == "1":
        raise HTTPException(400, "The main group cannot be closed")
    b = await session(uid, whole=True)
    await bcall(b.group_close(gid=gid), 404)
    await persist(uid, b)
    return {"ok": True}


@api.post("/runs/pause-all")
async def runs_pause_all(uid: str = Depends(uid_of)):
    runs = await db.runs.find({"user_id": uid, "status": "running"}, {"_id": 0}).to_list(50)
    for run in runs:
        await db.runs.update_one({"id": run["id"], "status": "running"}, {"$set": {"status": "paused"}})
        with suppress(Exception):
            s = await resolve_session(uid, run.get("target", "cloud"), run.get("group_id", "1"))
            await s.corrections_start()
    return {"paused": len(runs)}


@api.post("/runs/resume-all")
async def runs_resume_all(uid: str = Depends(uid_of)):
    need_key()
    runs = await db.runs.find({"user_id": uid, "status": "paused"}, {"_id": 0, "id": 1}).to_list(50)
    done, errors = 0, []
    for run in runs:
        try:
            await runs_resume(run["id"], uid)
            done += 1
        except HTTPException as e:
            errors.append(str(e.detail))
    return {"resumed": done, "errors": errors[:5]}


# ---------------- recording ----------------
class NoteIn(BaseModel):
    text: str


@api.post("/record/start")
async def record_start(uid: str = Depends(uid_of), gid: str = Depends(gid_of)):
    run = await active_run(uid, gid)
    if run and run["status"] == "running":
        raise HTTPException(409, "Shadow is running a task in this workspace. Pause or stop it first.")
    s = await session(uid, gid=gid)
    await bcall(s.record_start())
    return {"ok": True}


@api.post("/record/note")
async def record_note(body: NoteIn, uid: str = Depends(uid_of), gid: str = Depends(gid_of)):
    s = await session(uid, gid=gid)
    await bcall(s.record_note(text=body.text))
    return {"ok": True}


@api.post("/record/stop")
async def record_stop(uid: str = Depends(uid_of), gid: str = Depends(gid_of)):
    s = await session(uid, gid=gid)
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
    await db.schedules.delete_many({"user_id": uid, "skill_id": sid})
    return {"ok": True}


# ---------------- runs ----------------
class RunIn(BaseModel):
    command: Optional[str] = ""
    skill_id: Optional[str] = None
    mode: Optional[str] = "real"


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
async def runs_create(body: RunIn, uid: str = Depends(uid_of), gid: str = Depends(gid_of)):
    need_key()
    cur = await active_run(uid, gid)
    if cur and cur["status"] == "waiting_input" and body.command and body.mode != "preview":
        return await runs_reply(cur["id"], ReplyIn(text=body.command), uid)
    if body.mode == "preview" and not body.skill_id:
        raise HTTPException(400, "Pick a skill to preview")
    return await create_run(uid, body.skill_id, body.command, await target_of(uid), mode=body.mode or "real", gid=gid)


async def create_run(uid, skill_id, command, target, mode="real", schedule_id=None, gid="1"):
    if await active_run(uid, gid):
        raise HTTPException(409, "A task is already in progress in this workspace. Finish, stop or resume it, or open another workspace.")
    s = await session(uid, target, gid)
    if (await bcall(s.state(), 409)).get("recording"):
        raise HTTPException(409, "Stop recording first")
    skill = None
    if skill_id:
        skill = await db.skills.find_one({"id": skill_id, "user_id": uid}, {"_id": 0})
        if not skill:
            raise HTTPException(404, "Skill not found")
    base = f'Run skill "{skill["name"]}"' if skill else ""
    extra = (command or "").strip()
    goal = (f"{base}. {extra}" if base and extra and schedule_id else extra or base)
    if not goal:
        raise HTTPException(400, "Tell Shadow what to do")
    if mode == "preview":
        goal = f'Preview skill "{skill["name"]}"'
    now = sb.now_iso()
    run = {"id": str(uuid.uuid4()), "user_id": uid, "goal": goal, "skill_id": skill["id"] if skill else None,
           "skill_name": skill["name"] if skill else None, "loaded_skills": [skill["id"]] if skill else [],
           "status": "running", "plan": [], "scratch": {}, "messages": [], "corrections": [], "pending": None,
           "step_count": 0, "summary": "", "target": target, "mode": "preview" if mode == "preview" else "real",
           "tables": [], "schedule_id": schedule_id, "trigger": "schedule" if schedule_id else "manual",
           "group_id": gid, "created_at": now, "updated_at": now}
    await db.runs.insert_one(run)
    run.pop("_id", None)
    await bcall(s.clear_events())
    engine.start(run["id"], uid)
    return run


@api.get("/runs")
async def runs_list(uid: str = Depends(uid_of)):
    return await db.runs.find({"user_id": uid}, {"_id": 0, "scratch": 0, "tables": 0}).sort("created_at", -1).to_list(100)


@api.get("/runs/active")
async def runs_active(uid: str = Depends(uid_of), gid: str = Depends(gid_of)):
    return {"run": await active_run(uid, gid)}


@api.get("/runs/{rid}")
async def runs_get(rid: str, uid: str = Depends(uid_of)):
    run = await get_run(rid, uid)
    run["steps"] = await db.run_steps.find({"run_id": rid}, {"_id": 0}).sort("idx", -1).to_list(200)
    run["tables"] = [{"name": t["name"], "columns": t["columns"], "row_count": len(t["rows"]), "rows": t["rows"][-100:]}
                     for t in run.get("tables") or []]
    return run


def _safe_cell(v):
    v = "" if v is None else str(v)
    return "'" + v if v[:1] in ("=", "+", "-", "@", "\t", "\r") else v


@api.get("/runs/{rid}/export")
async def runs_export(rid: str, uid: str = Depends(uid_of)):
    import io
    import openpyxl
    from openpyxl.styles import Font
    run = await get_run(rid, uid)
    tables = run.get("tables") or []
    if not tables:
        raise HTTPException(404, "This task has no results table")
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    used = set()
    for t in tables:
        title = re.sub(r"[\[\]:*?/\\]", "_", t["name"])[:28] or "Results"
        while title in used:
            title += "_"
        used.add(title)
        ws = wb.create_sheet(title)
        ws.append(t["columns"])
        for c in ws[1]:
            c.font = Font(bold=True)
        for r in t["rows"]:
            ws.append([_safe_cell(r.get(col, "")) for col in t["columns"]])
        for i, col in enumerate(t["columns"], 1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = min(50, max(12, len(col) + 4))
    buf = io.BytesIO()
    wb.save(buf)
    name = f"shadow-results-{run['created_at'][:10]}.xlsx"
    return Response(buf.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


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
    s = await session(uid, run.get("target", "cloud"), run.get("group_id", "1"))
    await bcall(s.corrections_start())
    return {"ok": True}


@api.post("/runs/{rid}/resume")
async def runs_resume(rid: str, uid: str = Depends(uid_of)):
    need_key()
    run = await get_run(rid, uid)
    if run["status"] not in ("paused", "failed", "stopped"):
        raise HTTPException(400, "Cannot resume")
    gid = run.get("group_id", "1")
    other = await active_run(uid, gid)
    if other and other["id"] != rid:
        raise HTTPException(409, "Another task is active in that group. Stop it first.")
    b = await session(uid, run.get("target", "cloud"), whole=True)
    await bcall(b.group_new(name=f"Resumed: {run['goal']}"[:40], url="", gid=gid), 409)
    s = b.group(gid)
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
        s = await resolve_session(uid, run.get("target", "cloud"), run.get("group_id", "1"))
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
            "online": online, "info": (conn.info if online else d.get("info")) or {},
            "last_update": d.get("last_update"), "update_history": list(reversed(d.get("update_history") or []))[:5]}


@api.get("/target")
async def target_get(uid: str = Depends(uid_of)):
    conn = hub.get(uid)
    return {"target": await target_of(uid), "helper_online": bool(conn),
            "helper": {"name": conn.device.get("name"), "info": conn.info, "last_update": conn.device.get("last_update")} if conn else None}


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
    asyncio.create_task(restore_laptop(uid, conn))
    try:
        while True:
            msg = await ws.receive_json()
            if "id" in msg:
                conn.resolve(msg)
            elif msg.get("event") == "hello":
                conn.info = msg.get("info") or {}
                upd = {"$set": {"info": conn.info, "last_seen": sb.now_iso()}}
                old_v, new_v = (dev.get("info") or {}).get("version"), conn.info.get("version")
                if old_v and new_v and sched_version(new_v) > sched_version(old_v):
                    entry = {"from": old_v, "to": new_v, "at": sb.now_iso()}
                    upd["$set"]["last_update"] = entry
                    upd["$push"] = {"update_history": {"$each": [entry], "$slice": -10}}
                    dev["last_update"] = conn.device["last_update"] = entry
                dev["info"] = conn.info
                await db.devices.update_one({"id": dev["id"]}, upd)
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        hub.unregister(uid, conn)
        conn.fail_all()
        await db.devices.update_one({"id": dev["id"]}, {"$set": {"last_seen": sb.now_iso()}})


async def restore_laptop(uid, conn):
    groups = await sb.load_workspaces(db, uid, "laptop")
    if groups:
        with suppress(Exception):
            await RemoteSession(conn).groups_restore(groups=groups)


async def workspace_saver():
    while True:
        await asyncio.sleep(20)
        for uid, conn in list(hub._conns.items()):
            with suppress(Exception):
                await persist(uid, RemoteSession(conn), "laptop")


# ---------------- schedules ----------------
class ScheduleIn(BaseModel):
    skill_id: str
    days: List[int]
    time: str
    timezone: str
    target: str = "laptop"
    instructions: Optional[str] = ""
    enabled: bool = True


def _check_schedule(body: ScheduleIn):
    from zoneinfo import ZoneInfo
    if not body.days or any(d not in range(7) for d in body.days):
        raise HTTPException(400, "Pick at least one day")
    if not re.fullmatch(r"([01]\d|2[0-3]):(00|15|30|45)", body.time):
        raise HTTPException(400, "Time must be on a quarter hour, e.g. 08:00 or 08:15")
    if body.target not in ("laptop", "cloud"):
        raise HTTPException(400, "Unknown target")
    try:
        ZoneInfo(body.timezone)
    except Exception:
        raise HTTPException(400, "Unknown time zone")


async def _schedule_doc(body: ScheduleIn, uid):
    sk = await db.skills.find_one({"id": body.skill_id, "user_id": uid}, {"_id": 0, "name": 1})
    if not sk:
        raise HTTPException(404, "Skill not found")
    nxt = sched.compute_next(sorted(set(body.days)), body.time, body.timezone) if body.enabled else None
    return {**body.model_dump(), "days": sorted(set(body.days)), "skill_name": sk["name"],
            "next_run_at": nxt.isoformat() if nxt else None, "updated_at": sb.now_iso()}


@api.get("/schedules")
async def schedules_list(uid: str = Depends(uid_of)):
    return await db.schedules.find({"user_id": uid}, {"_id": 0}).sort("created_at", -1).to_list(100)


@api.post("/schedules")
async def schedules_create(body: ScheduleIn, uid: str = Depends(uid_of)):
    _check_schedule(body)
    doc = {"id": str(uuid.uuid4()), "user_id": uid, **(await _schedule_doc(body, uid)), "created_at": sb.now_iso(),
           "last_run_at": None, "last_status": None, "last_run_id": None, "last_note": ""}
    await db.schedules.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.put("/schedules/{sid}")
async def schedules_update(sid: str, body: ScheduleIn, uid: str = Depends(uid_of)):
    _check_schedule(body)
    r = await db.schedules.update_one({"id": sid, "user_id": uid}, {"$set": await _schedule_doc(body, uid)})
    if not r.matched_count:
        raise HTTPException(404, "Not found")
    return await db.schedules.find_one({"id": sid, "user_id": uid}, {"_id": 0})


@api.delete("/schedules/{sid}")
async def schedules_delete(sid: str, uid: str = Depends(uid_of)):
    r = await db.schedules.delete_one({"id": sid, "user_id": uid})
    if not r.deleted_count:
        raise HTTPException(404, "Not found")
    return {"ok": True}


async def _scheduled_start(uid, skill_id, instructions, target, schedule_id):
    if not llm_key():
        raise HTTPException(400, "OpenAI key missing")
    try:
        return await create_run(uid, skill_id, instructions, target, schedule_id=schedule_id)
    except HTTPException as e:
        if e.status_code != 409 or "laptop" in str(e.detail).lower():
            raise
    sk = await db.skills.find_one({"id": skill_id, "user_id": uid}, {"_id": 0, "name": 1}) or {}
    b = await session(uid, target, whole=True)
    g = await bcall(b.group_new(name=f"Scheduled: {sk.get('name', 'skill')}"[:40], url=""), 409)
    return await create_run(uid, skill_id, instructions, target, schedule_id=schedule_id, gid=g["id"])


_cron_seen: dict = {}


@app.post("/api/cron/schedules")
async def cron_schedules(request: Request):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    import hmac
    secret = os.environ.get("WEBHOOK_CRON_SECRET", "")
    auth = request.headers.get("authorization", "")
    if not secret or not auth.startswith("Bearer ") or not hmac.compare_digest(auth[7:], secret):
        raise HTTPException(401, "Unauthorized")
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        raise HTTPException(400, "Invalid body")
    run_id = request.headers.get("x-webhook-id") or body.get("run_id") or str(uuid.uuid4())
    if run_id in _cron_seen:
        return {"ok": True, "duplicate": True}
    _cron_seen[run_id] = True
    if len(_cron_seen) > 500:
        _cron_seen.pop(next(iter(_cron_seen)))
    asyncio.create_task(sched.run_due(db, _scheduled_start, lambda u: bool(hub.get(u))))
    return {"ok": True}


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
    app.state.autosave = asyncio.create_task(sb.autosave(db))
    app.state.ws_saver = asyncio.create_task(workspace_saver())
    app.state.browser_install = asyncio.create_task(sb.ensure_browser_installed())
    await db.runs.update_many({"group_id": {"$exists": False}}, {"$set": {"group_id": "1"}})
    await db.runs.update_many({"status": "running"}, {"$set": {"status": "paused", "summary": "Interrupted by a restart — press Resume to continue from the last step."}})


@app.on_event("shutdown")
async def shutdown():
    app.state.index_task.cancel()
    with suppress(asyncio.CancelledError):
        await app.state.index_task
    await sb.close_all(db)
    client.close()
