"""Passwordless visitor accounts, independent of the booking administrator."""
import hashlib
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from fastapi import HTTPException
from sqlalchemy import select, delete
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from app.models import CalendarVisitor, CalendarLoginSession, CalendarOpenedDoor, CalendarLoginRate, CalendarLoginLink

COOKIE = "jul2026_session"
SESSION_DAYS = 90
YEAR = 2026


def utcnow():
    # Naive UTC works consistently with the project's SQLite and PostgreSQL types.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def public_url():
    value = os.getenv("CHRISTMAS_PUBLIC_URL", "https://iebeltoft.dk").strip().rstrip("/")
    parsed = urlsplit(value)
    local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if (parsed.scheme != "https" and not (local and parsed.scheme == "http")) or not parsed.netloc or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        raise HTTPException(503, "Kalenderens loginadresse er ikke konfigureret korrekt.")
    return value


def validate_email(value):
    value = value.strip().lower()
    if len(value) > 254 or not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+", value):
        raise HTTPException(422, "Skriv en gyldig e-mailadresse.")
    local, domain = value.rsplit("@", 1)
    if len(local) > 64 or local.startswith(".") or local.endswith(".") or ".." in local or any(len(label) > 63 for label in domain.split(".")):
        raise HTTPException(422, "Skriv en gyldig e-mailadresse.")
    return value


def require_same_origin(request):
    # Custom header cannot be submitted by a cross-site HTML form. No CORS allowed.
    origin = request.headers.get("origin")
    if request.headers.get("x-calendar-request") != "1" or (origin and origin.rstrip("/") != str(request.base_url).rstrip("/")):
        raise HTTPException(403, "Åbn kalenderen igen, og prøv derfra.")


def insert_for(db, model):
    return (postgres_insert if db.bind.dialect.name == "postgresql" else sqlite_insert)(model)


def visitor(request, db):
    raw = request.cookies.get(COOKIE, "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", raw):
        return None
    return db.scalar(select(CalendarVisitor).join(CalendarLoginSession, CalendarLoginSession.visitor_id == CalendarVisitor.id).where(CalendarLoginSession.token_hash == digest(raw), CalendarLoginSession.expires_at > utcnow()))


def opened_days(db, visitor_id):
    return list(db.scalars(select(CalendarOpenedDoor.day).where(CalendarOpenedDoor.visitor_id == visitor_id, CalendarOpenedDoor.year == YEAR).order_by(CalendarOpenedDoor.day)))


def add_opened_days(db, visitor_id, days):
    for day in set(days):
        db.execute(insert_for(db, CalendarOpenedDoor).values(visitor_id=visitor_id, year=YEAR, day=day).on_conflict_do_nothing())
    db.commit()
    return opened_days(db, visitor_id)


def limit_login_requests(db, email, ip):
    now = utcnow()
    # Durable, atomic counters also work across workers and after restarts.
    for scope, value, seconds, limit in [("email-minute", email, 60, 1), ("email-hour", email, 3600, 5), ("ip-hour", ip, 3600, 20)]:
        window = int(now.replace(tzinfo=timezone.utc).timestamp()) // seconds
        bucket = digest(f"{scope}:{value}:{window}")
        stmt = insert_for(db, CalendarLoginRate).values(bucket=bucket, count=1, expires_at=now + timedelta(seconds=seconds * 2))
        stmt = stmt.on_conflict_do_update(index_elements=[CalendarLoginRate.bucket], set_={"count": CalendarLoginRate.count + 1}, where=CalendarLoginRate.count < limit)
        if db.execute(stmt).rowcount == 0:
            db.rollback()
            raise HTTPException(429, "Der er bedt om flere loginlinks. Vent lidt, og prøv igen.", headers={"Retry-After": "60"})
    db.execute(delete(CalendarLoginRate).where(CalendarLoginRate.expires_at < now))
    db.execute(delete(CalendarLoginLink).where(CalendarLoginLink.expires_at < now))
    db.execute(delete(CalendarLoginSession).where(CalendarLoginSession.expires_at < now))
    db.commit()
