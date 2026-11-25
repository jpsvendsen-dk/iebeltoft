"""Administrator-only visitor access and door-click history."""
import secrets
from datetime import timezone
from fastapi import APIRouter, Request, Depends, Form, Query, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import CalendarVisitor, CalendarDoorEvent
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
    messages = {"added": "Profilen er tilføjet.", "existing": "E-mailadressen findes allerede. Adgangen er bevaret; brug Gem adgang i listen for at ændre den.", "updated": "Brugerens adgang er gemt."}
    return templates.TemplateResponse(request, "admin/christmas_settings.html", {"request": request, "aktiv_side": "christmas_settings", "people": people, "q": q, "page": page, "total": count, "has_next": page * PAGE_SIZE < count, "csrf": csrf_token(request), "message": messages.get(request.query_params.get("saved"), "")}, headers={"Cache-Control": "no-store"})


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


@router.get("/historik")
def history(request: Request, email: str = Query(default="", max_length=254), day: str = Query(default="", pattern=r"^(?:[1-9]|1[0-9]|2[0-4])?$"), page: int = Query(default=1, ge=1), db: Session = Depends(get_db)):
    redirect = kræv_login(request)
    if redirect:
        return redirect
    email = email.strip().lower()
    day = int(day) if day else None
    query = select(CalendarDoorEvent, CalendarVisitor.email).join(CalendarVisitor).where(CalendarDoorEvent.year == YEAR)
    if email:
        query = query.where(CalendarVisitor.email == email)
    if day is not None:
        query = query.where(CalendarDoorEvent.day == day)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(query.order_by(CalendarDoorEvent.clicked_at.desc(), CalendarDoorEvent.id.desc()).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)).all()
    labels = {"opened": "Åbnet", "reopened": "Åbnet igen", "locked": "Afvist – låst låge"}
    events = [{"email": address, "day": event.day, "time": event.clicked_at.replace(tzinfo=timezone.utc).astimezone(TZ).strftime("%d.%m.%Y kl. %H:%M:%S %Z"), "iso": event.clicked_at.replace(tzinfo=timezone.utc).isoformat(), "result": labels[event.result]} for event, address in rows]
    return templates.TemplateResponse(request, "admin/christmas_history.html", {"request": request, "aktiv_side": "christmas_history", "events": events, "email": email, "day": day, "page": page, "total": total, "has_next": page * PAGE_SIZE < total}, headers={"Cache-Control": "no-store"})
