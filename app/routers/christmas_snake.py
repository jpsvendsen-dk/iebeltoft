"""Public named Snake scores; the server replays every saved game."""
import hashlib
import secrets
import unicodedata
from datetime import timedelta
from uuid import uuid4, UUID
from typing import Literal
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, StrictInt, StrictBool
from sqlalchemy import select, update, delete, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import CalendarSnakeProfile as Profile, CalendarSnakeRound as Round, CalendarSnakeEvent
from app.services import christmas_accounts as accounts
from app.services import christmas_snake as rules
from app.services.calendar_client import client_metadata

router = APIRouter(prefix="/Jul2026/api/snake")
HEADERS = {"Cache-Control": "no-store"}


class Identity(BaseModel):
    account_id: StrictInt = Field(gt=0)


class Start(Identity):
    rules_version: StrictInt = Field(default=1, ge=1, le=3)


class Click(BaseModel):
    event_id: UUID
    action: Literal['open', 'replay']


@router.post("/events")
def log_click(body: Click, request: Request, db: Session = Depends(get_db)):
    accounts.require_same_origin(request)
    person = accounts.visitor(request, db)
    person_id = person.id if person else None
    event_id = str(body.event_id)
    inserted = db.execute(accounts.insert_for(db, CalendarSnakeEvent).values(id=event_id, visitor_id=person_id, year=accounts.YEAR, action=body.action, clicked_at=accounts.utcnow(), **client_metadata(request)).on_conflict_do_nothing(index_elements=[CalendarSnakeEvent.id])).rowcount
    if not inserted:
        original = db.get(CalendarSnakeEvent, event_id)
        if original.visitor_id != person_id or original.action != body.action:
            db.rollback()
            raise HTTPException(409, "Klikket tilhører en anden hændelse.")
    db.commit()
    return JSONResponse({"ok": True}, headers=HEADERS)


class Preferences(Identity):
    display_name: str = Field(default="", max_length=40)
    is_public: StrictBool = True


class Turn(BaseModel):
    tick: StrictInt = Field(ge=1, le=rules.MAX_TICKS)
    direction: StrictInt = Field(ge=0, le=3)


class Finish(Identity):
    ticks: StrictInt = Field(ge=1, le=rules.MAX_TICKS)
    turns: list[Turn] = Field(max_length=rules.MAX_TICKS)


def person_for(request, db, account_id=None):
    person = accounts.visitor(request, db)
    if person is None:
        raise HTTPException(401, "Log ind for at gemme rekorden på din profil.")
    if account_id is not None and person.id != account_id:
        raise HTTPException(409, "En anden profil er logget ind. Åbn spillet igen.")
    return person


def ensure_profile(db, visitor_id):
    db.execute(accounts.insert_for(db, Profile).values(visitor_id=visitor_id, year=accounts.YEAR).on_conflict_do_nothing(index_elements=[Profile.visitor_id, Profile.year]))


def profile_data(db, visitor_id):
    profile = db.get(Profile, (visitor_id, accounts.YEAR))
    return {"account_id": visitor_id, "best_score": profile.best_score if profile else 0, "display_name": (profile.display_name or "") if profile else "", "is_public": True}


@router.get("/profile")
def profile(request: Request, db: Session = Depends(get_db)):
    person = accounts.visitor(request, db)
    return JSONResponse({"profile": profile_data(db, person.id) if person else None}, headers=HEADERS)


@router.post("/profile")
def preferences(body: Preferences, request: Request, db: Session = Depends(get_db)):
    accounts.require_same_origin(request)
    person = person_for(request, db, body.account_id)
    name = " ".join(unicodedata.normalize("NFKC", body.display_name).split())
    if name and (not 2 <= len(name) <= 20 or not all(c.isalpha() or c.isdecimal() or c in " -_" for c in name) or not any(c.isalnum() for c in name)):
        raise HTTPException(422, "Vælg 2–20 tegn: bogstaver, tal, mellemrum, bindestreg eller understregning.")
    if not name:
        raise HTTPException(422, "Vælg et spillernavn for at deltage på toplisten.")
    try:
        ensure_profile(db, person.id)
        db.execute(update(Profile).where(Profile.visitor_id == person.id, Profile.year == accounts.YEAR).values(display_name=name, name_key=name.casefold(), is_public=True))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Spillernavnet er optaget. Vælg et andet.")
    return JSONResponse({"profile": profile_data(db, person.id)}, headers=HEADERS)


@router.get("/leaderboard")
def leaderboard(db: Session = Depends(get_db)):
    people = db.scalars(select(Profile).where(Profile.year == accounts.YEAR, Profile.display_name.is_not(None), Profile.display_name != "", Profile.best_score > 0).order_by(Profile.best_score.desc(), Profile.achieved_at.asc(), Profile.visitor_id.asc()).limit(10)).all()
    return JSONResponse({"players": [{"rank": i + 1, "name": p.display_name, "score": p.best_score} for i, p in enumerate(people)]}, headers=HEADERS)


@router.post("/rounds")
def start(body: Start, request: Request, db: Session = Depends(get_db)):
    accounts.require_same_origin(request)
    person = person_for(request, db, body.account_id)
    now = accounts.utcnow()
    recent = db.scalar(select(func.count()).select_from(Round).where(Round.visitor_id == person.id, Round.started_at > now - timedelta(minutes=1)))
    if recent >= 20:
        raise HTTPException(429, "Vent et øjeblik, før du starter flere spil.")
    # Old abandoned rounds contain no record and can be removed on the next start.
    db.execute(delete(Round).where(Round.visitor_id == person.id, Round.started_at < now - timedelta(days=2)))
    round = Round(id=str(uuid4()), visitor_id=person.id, year=accounts.YEAR, seed=secrets.randbelow(2147483646) + 1, started_at=now, rules_version=body.rules_version)
    db.add(round)
    db.commit()
    return JSONResponse({"round_id": round.id, "seed": round.seed, "max_ticks": rules.MAX_TICKS, "rules_version": round.rules_version}, headers=HEADERS)


@router.post("/rounds/{round_id}/finish")
def finish(round_id: UUID, body: Finish, request: Request, db: Session = Depends(get_db)):
    accounts.require_same_origin(request)
    person = person_for(request, db, body.account_id)
    round = db.get(Round, str(round_id))
    if not round or round.visitor_id != person.id or round.year != accounts.YEAR:
        raise HTTPException(404, "Spilrunden findes ikke på din profil.")
    signature = hashlib.sha256(body.model_dump_json().encode()).hexdigest()
    if round.finished_at:
        if round.submission_hash != signature:
            raise HTTPException(409, "Spilrunden er allerede gemt med et andet resultat.")
        return JSONResponse({"score": round.score, "profile": profile_data(db, person.id)}, headers=HEADERS)
    now = accounts.utcnow()
    if now - round.started_at > timedelta(hours=2):
        raise HTTPException(422, "Spilrunden er udløbet. Start et nyt spil.")
    try:
        game = rules.replay(round.seed, body.ticks, body.turns, round.rules_version)
    except ValueError as error:
        raise HTTPException(422, str(error))
    if game.elapsed_ms > (now - round.started_at).total_seconds() * 1000 + 250:
        raise HTTPException(422, "Spillets varighed passer ikke med resultatet.")
    claimed = db.execute(update(Round).where(Round.id == round.id, Round.finished_at.is_(None)).values(finished_at=now, score=game.score, submission_hash=signature)).rowcount
    if not claimed:
        db.rollback()
        raise HTTPException(409, "Spilrunden er allerede behandlet. Prøv at gemme igen.")
    ensure_profile(db, person.id)
    db.execute(update(Profile).where(Profile.visitor_id == person.id, Profile.year == accounts.YEAR, Profile.best_score < game.score).values(best_score=game.score, achieved_at=now))
    db.commit()
    return JSONResponse({"score": game.score, "profile": profile_data(db, person.id)}, headers=HEADERS)
