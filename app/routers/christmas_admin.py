"""Administrator-only visitor access and door-click history."""
import secrets
from datetime import timezone
from fastapi import APIRouter, Request, Depends, Form, Query, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func, update, delete
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import CalendarVisitor, CalendarDoorEvent, CalendarLoginEvent, CalendarOpenedDoor
from app.auth import kræv_login
from app.services import christmas_accounts as accounts
from app.services.christmas_access import YEAR, TZ

router = APIRouter(prefix="/admin/jul2026")
templates = Jinja2Templates(directory="app/templates")
PAGE_SIZE = 50


def csrf_token(request):
    if "calendar_csrf" not in request.session:
        request.session["calendar_csrf"] = secrets.token_urlsafe(32)
    return request.session["calendar_csrf"]


def verify_admin_form(request, token):
    if request.session.get("admin") is not True:
        raise HTTPException(401, "Log ind som administrator.")
    expected = request.session.get("calendar_csrf", "")
    if not expected or not secrets.compare_digest(expected, token):
        raise HTTPException(403, "Formularen er udløbet. Genindlæs siden, og prøv igen.")


@router.get("/indstillinger")
def settings(request: Request, q: str = Query(default="", max_length=254), page: int = Query(default=1, ge=1), db: Session = Depends(get_db)):
    redirect = kræv_login(request)
    if redirect:
        return redirect
    q = q.strip().lower()
    condition = CalendarVisitor.email.contains(q, autoescape=True)
    count = db.scalar(select(func.count()).select_from(CalendarVisitor).where(condition))
    people = db.scalars(select(CalendarVisitor).where(condition).order_by(CalendarVisitor.email).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)).all()
    ids = [person.id for person in people]
    door_counts = dict(db.execute(select(CalendarDoorEvent.visitor_id, func.count()).where(CalendarDoorEvent.visitor_id.in_(ids), CalendarDoorEvent.year == YEAR).group_by(CalendarDoorEvent.visitor_id)).all()) if ids else {}
    login_counts = dict(db.execute(select(CalendarLoginEvent.visitor_id, func.count()).where(CalendarLoginEvent.visitor_id.in_(ids), CalendarLoginEvent.year == YEAR).group_by(CalendarLoginEvent.visitor_id)).all()) if ids else {}
    messages = {"added": "Profilen er tilføjet.", "existing": "E-mailadressen findes allerede. Adgangen er bevaret; brug Gem adgang i listen for at ændre den.", "updated": "Brugerens adgang er gemt.", "reset": "Alle brugerens låger er lukket. Historikken, login og adgangen er bevaret. Kalenderen opdateres ved næste genindlæsning eller automatiske opdatering."}
    return templates.TemplateResponse(request, "admin/christmas_settings.html", {"request": request, "aktiv_side": "christmas_settings", "people": people, "door_counts": door_counts, "login_counts": login_counts, "q": q, "page": page, "total": count, "has_next": page * PAGE_SIZE < count, "csrf": csrf_token(request), "message": messages.get(request.query_params.get("saved"), "")}, headers={"Cache-Control": "no-store"})


@router.post("/indstillinger/tilfoej")
def add_person(request: Request, email: str = Form(..., max_length=254), early_access: bool = Form(False), csrf: str = Form(...), db: Session = Depends(get_db)):
    verify_admin_form(request, csrf)
    email = accounts.validate_email(email)
    # Existing profiles must be changed explicitly in their own form.
    added = db.execute(accounts.insert_for(db, CalendarVisitor).values(email=email, early_access=early_access).on_conflict_do_nothing(index_elements=[CalendarVisitor.email])).rowcount
    db.commit()
    return RedirectResponse("/admin/jul2026/indstillinger?saved=" + ("added" if added else "existing"), status_code=303)


@router.post("/indstillinger/brugere/{person_id}")
def change_access(person_id: int, request: Request, csrf: str = Form(...), early_access: bool = Form(False), db: Session = Depends(get_db)):
    verify_admin_form(request, csrf)
    person = db.get(CalendarVisitor, person_id)
    if person is None:
        raise HTTPException(404, "Brugeren findes ikke.")
    person.early_access = early_access
    db.commit()
    return RedirectResponse("/admin/jul2026/indstillinger?saved=updated", status_code=303)


@router.get("/indstillinger/brugere/{person_id}/nulstil")
def reset_confirmation(person_id: int, request: Request, db: Session = Depends(get_db)):
    redirect = kræv_login(request)
    if redirect:
        return redirect
    person = db.get(CalendarVisitor, person_id)
    if person is None:
        raise HTTPException(404, "Brugeren findes ikke.")
    opened_count = db.scalar(select(func.count()).select_from(CalendarOpenedDoor).where(CalendarOpenedDoor.visitor_id == person_id, CalendarOpenedDoor.year == YEAR))
    return templates.TemplateResponse(request, "admin/christmas_reset.html", {"request": request, "aktiv_side": "christmas_settings", "person": person, "opened_count": opened_count, "csrf": csrf_token(request)}, headers={"Cache-Control": "no-store"})


@router.post("/indstillinger/brugere/{person_id}/nulstil")
def reset_progress(person_id: int, request: Request, csrf: str = Form(...), confirm: str = Form(...), db: Session = Depends(get_db)):
    verify_admin_form(request, csrf)
    if confirm != "reset":
        raise HTTPException(400, "Bekræft nulstillingen på brugerens nulstillingsside.")
    result = db.execute(update(CalendarVisitor).where(CalendarVisitor.id == person_id).values(progress_version=CalendarVisitor.progress_version + 1))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(404, "Brugeren findes ikke.")
    db.execute(delete(CalendarOpenedDoor).where(CalendarOpenedDoor.visitor_id == person_id, CalendarOpenedDoor.year == YEAR))
    db.commit()
    return RedirectResponse("/admin/jul2026/indstillinger?saved=reset", status_code=303)


@router.get("/historik")
def history(request: Request, email: str = Query(default="", max_length=254), day: str = Query(default="", pattern=r"^(?:[1-9]|1[0-9]|2[0-4])?$"), kind: str = Query(default="doors", pattern="^(doors|login)$"), page: int = Query(default=1, ge=1), db: Session = Depends(get_db)):
    redirect = kræv_login(request)
    if redirect:
        return redirect
    email = email.strip().lower()
    day = int(day) if day and kind == "doors" else None
    model = CalendarLoginEvent if kind == "login" else CalendarDoorEvent
    stamp = CalendarLoginEvent.logged_at if kind == "login" else CalendarDoorEvent.clicked_at
    query = select(model, CalendarVisitor.email).join(CalendarVisitor).where(model.year == YEAR)
    if email:
        query = query.where(CalendarVisitor.email == email)
    if day is not None:
        query = query.where(CalendarDoorEvent.day == day)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(query.order_by(stamp.desc(), model.id.desc()).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)).all()
    labels = {"opened": "Åbnet", "reopened": "Åbnet igen", "locked": "Afvist – låst låge"}
    events = []
    for event, address in rows:
        timestamp = event.logged_at if kind == "login" else event.clicked_at
        events.append({"email": address, "day": None if kind == "login" else event.day, "time": timestamp.replace(tzinfo=timezone.utc).astimezone(TZ).strftime("%d.%m.%Y kl. %H:%M:%S %Z"), "iso": timestamp.replace(tzinfo=timezone.utc).isoformat(), "result": "Logget ind" if kind == "login" else labels[event.result], "ip": event.ip_address, "device": event.device_type, "user_agent": event.user_agent})
    return templates.TemplateResponse(request, "admin/christmas_history.html", {"request": request, "aktiv_side": "christmas_history", "events": events, "email": email, "day": day, "kind": kind, "page": page, "total": total, "has_next": page * PAGE_SIZE < total}, headers={"Cache-Control": "no-store"})
