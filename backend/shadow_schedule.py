import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

log = logging.getLogger("shadow.schedule")


def compute_next(days, time_hhmm, tz_name, after: datetime = None):
    """Next UTC datetime on one of `days` (0=Sunday..6=Saturday) at local HH:MM, strictly after `after`."""
    tz = ZoneInfo(tz_name)
    after = (after or datetime.now(timezone.utc)).astimezone(tz)
    hh, mm = (int(x) for x in time_hhmm.split(":"))
    for i in range(0, 8):
        d = after.date() + timedelta(days=i)
        cand = datetime(d.year, d.month, d.day, hh, mm, tzinfo=tz)
        if (cand.isoweekday() % 7) in days and cand > after:
            return cand.astimezone(timezone.utc)
    return None


async def run_due(db, start_run, helper_online):
    """Start every enabled schedule whose time has come. Claims each slot atomically so it runs once."""
    now = datetime.now(timezone.utc)
    due = await db.schedules.find({"enabled": True, "next_run_at": {"$lte": now.isoformat()}}, {"_id": 0}).to_list(500)
    for sc in due:
        nxt = compute_next(sc["days"], sc["time"], sc["timezone"], now)
        claimed = await db.schedules.update_one({"id": sc["id"], "next_run_at": sc["next_run_at"]},
                                                {"$set": {"next_run_at": nxt.isoformat() if nxt else None}})
        if not claimed.modified_count:
            continue
        target = "laptop" if sc.get("target") == "laptop" and helper_online(sc["user_id"]) else "cloud"
        note = "" if target == sc.get("target") else "Laptop was offline, so it ran in the cloud."
        try:
            try:
                run = await start_run(sc["user_id"], sc["skill_id"], sc.get("instructions", ""), target, sc["id"])
            except Exception as e:
                if target != "laptop" or "laptop" not in str(getattr(e, "detail", e)).lower():
                    raise
                target, note = "cloud", "Laptop went offline, so it ran in the cloud."
                run = await start_run(sc["user_id"], sc["skill_id"], sc.get("instructions", ""), target, sc["id"])
            res = {"last_status": "started", "last_run_id": run["id"], "last_note": note}
        except Exception as e:
            res = {"last_status": "skipped", "last_run_id": None, "last_note": str(getattr(e, "detail", e))[:200]}
            log.warning("schedule %s skipped: %s", sc["id"], e)
        await db.schedules.update_one({"id": sc["id"]}, {"$set": {**res, "last_run_at": now.isoformat()}})
