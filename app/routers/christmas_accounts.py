import os
import re
import secrets
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, StrictInt
from sqlalchemy import select, update, delete
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import CalendarVisitor, CalendarLoginLink, CalendarLoginSession, CalendarLoginEvent
from app.services import christmas_accounts as accounts
from app.services.email import send_calendar_login
from app.services.christmas_access import allowed_day, today
from app.services.calendar_client import client_metadata

router = APIRouter(prefix="/Jul2026")
PRIVATE_HEADERS = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class LoginToken(BaseModel):
    token: str = Field(min_length=43, max_length=43)


class OpenedDoors(BaseModel):
    account_id: StrictInt = Field(gt=0)
    days: list[StrictInt] = Field(max_length=24)
    progress_version: StrictInt | None = Field(default=None, ge=0)


@router.get("/login")
def login_page():
    return FileResponse("static/jul2026/login.html", headers={**PRIVATE_HEADERS, "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"})


@router.post("/api/login/request")
def request_login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    accounts.require_same_origin(request)
    email = accounts.validate_email(body.email)
    base_url = accounts.public_url()
    if not os.getenv("RESEND_API_KEY", ""):
        raise HTTPException(503, "E-maillogin er ikke tilgængeligt lige nu. Du kan fortsat bruge kalenderen uden login.")
    accounts.limit_login_requests(db, email, request.client.host if request.client else "unknown")
    token = secrets.token_urlsafe(32)
    token_hash = accounts.digest(token)
    db.add(CalendarLoginLink(token_hash=token_hash, email=email, expires_at=accounts.utcnow() + timedelta(minutes=15)))
    db.commit()
    # A URL fragment keeps the secret out of HTTP access logs and Referer headers.
    if not send_calendar_login(email, f"{base_url}/Jul2026/login#token={token}"):
        db.execute(delete(CalendarLoginLink).where(CalendarLoginLink.token_hash == token_hash))
        db.commit()
        raise HTTPException(503, "Mailen kunne ikke sendes. Prøv igen senere. Dine låger er stadig gemt i denne browser.")
    return JSONResponse({"message": "Tjek din indbakke. Dit loginlink gælder i 15 minutter. Kig også i spam, hvis mailen ikke dukker op."}, headers=PRIVATE_HEADERS)


@router.post("/api/login/consume")
def consume_login(body: LoginToken, request: Request, db: Session = Depends(get_db)):
    accounts.require_same_origin(request)
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", body.token):
        raise HTTPException(400, "Loginlinket er ugyldigt eller udløbet. Bestil et nyt link.")
    now, token_hash = accounts.utcnow(), accounts.digest(body.token)
    # Conditional UPDATE ensures two concurrent requests cannot both redeem it.
    result = db.execute(update(CalendarLoginLink).where(CalendarLoginLink.token_hash == token_hash, CalendarLoginLink.used_at.is_(None), CalendarLoginLink.expires_at > now).values(used_at=now))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(400, "Loginlinket er ugyldigt, brugt eller udløbet. Bestil et nyt link.")
    link = db.get(CalendarLoginLink, token_hash)
    db.execute(accounts.insert_for(db, CalendarVisitor).values(email=link.email).on_conflict_do_nothing(index_elements=[CalendarVisitor.email]))
    person = db.scalar(select(CalendarVisitor).where(CalendarVisitor.email == link.email))
    session = secrets.token_urlsafe(32)
    db.add(CalendarLoginSession(token_hash=accounts.digest(session), visitor_id=person.id, expires_at=now + timedelta(days=accounts.SESSION_DAYS)))
    db.add(CalendarLoginEvent(visitor_id=person.id, year=accounts.YEAR, logged_at=now, **client_metadata(request)))
    db.commit()
    response = JSONResponse({"ok": True}, headers=PRIVATE_HEADERS)
    response.set_cookie(accounts.COOKIE, session, max_age=accounts.SESSION_DAYS * 86400, path="/Jul2026", httponly=True, secure=request.url.hostname not in {"localhost", "127.0.0.1", "::1"}, samesite="lax")
    return response


@router.get("/api/account")
def account(request: Request, db: Session = Depends(get_db)):
    person = accounts.visitor(request, db)
    return JSONResponse({"account": {"id": person.id, "email": person.email, "early_access": person.early_access, "progress_version": person.progress_version, "opened": accounts.opened_days(db, person.id)} if person else None}, headers=PRIVATE_HEADERS)


@router.post("/api/account/opened")
def save_opened(body: OpenedDoors, request: Request, db: Session = Depends(get_db)):
    accounts.require_same_origin(request)
    person = accounts.visitor(request, db)
    if not person:
        raise HTTPException(401, "Dit login er udløbet. Log ind igen for at gemme på tværs af enheder.")
    if person.id != body.account_id:
        raise HTTPException(409, "En anden kalender er blevet logget ind i denne browser. Opdatér siden.")
    accounts.require_progress_version(db, person, body.progress_version)
    available = allowed_day(today(), person)
    previous = set(accounts.opened_days(db, person.id))
    if any(day < 1 or day > 24 or (day > available and day not in previous) for day in body.days):
        raise HTTPException(422, "Kun låger, hvis dato er nået, kan gemmes.")
    opened = accounts.add_opened_days(db, person.id, body.days)
    return JSONResponse({"opened": opened}, headers=PRIVATE_HEADERS)


@router.post("/api/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    accounts.require_same_origin(request)
    raw = request.cookies.get(accounts.COOKIE, "")
    if raw:
        db.execute(delete(CalendarLoginSession).where(CalendarLoginSession.token_hash == accounts.digest(raw)))
        db.commit()
    response = JSONResponse({"ok": True}, headers=PRIVATE_HEADERS)
    response.delete_cookie(accounts.COOKIE, path="/Jul2026")
    return response
