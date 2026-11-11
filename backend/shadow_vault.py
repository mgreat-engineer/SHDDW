"""Encrypted password vault: logins are Fernet-encrypted at rest; the AI never receives the plain password."""
import hashlib
import hmac
import os
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from cryptography.fernet import Fernet


def _key() -> bytes:
    return os.environ["VAULT_KEY"].encode()


def origin_of(url: str) -> str:
    p = urlparse(url or "")
    return f"{p.scheme}://{p.netloc}".lower() if p.scheme in ("http", "https") and p.netloc else ""


def sha(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def _mac(pw_sha: str) -> str:
    return hmac.new(_key(), pw_sha.encode(), hashlib.sha256).hexdigest()


async def save(db, uid, origin, username, password):
    now = datetime.now(timezone.utc).isoformat()
    enc = Fernet(_key()).encrypt(password.encode()).decode()
    await db.passwords.update_one(
        {"user_id": uid, "origin": origin, "username": username},
        {"$set": {"password_enc": enc, "pw_mac": _mac(sha(password)), "updated_at": now},
         "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now}}, upsert=True)


async def already_saved(db, uid, origin, username, pw_sha) -> bool:
    return bool(await db.passwords.find_one({"user_id": uid, "origin": origin, "username": username, "pw_mac": _mac(pw_sha)}, {"_id": 1}))


async def logins_for(db, uid, origin):
    if not origin:
        return []
    return await db.passwords.find({"user_id": uid, "origin": origin}, {"_id": 0, "id": 1, "username": 1}).sort("updated_at", -1).to_list(20)


async def secret(db, uid, pid):
    d = await db.passwords.find_one({"user_id": uid, "id": pid}, {"_id": 0})
    if not d:
        return None
    return {"origin": d["origin"], "username": d["username"], "password": Fernet(_key()).decrypt(d["password_enc"].encode()).decode()}
