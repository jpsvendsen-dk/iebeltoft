from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from fastapi import Depends
from app.database import get_db
from app import models
from app.auth import kræv_login, ADMIN_PASSWORD
from app.services.saeson import generer_aarsoverblik, SAESON_FARVER
from decimal import Decimal, InvalidOperation
import datetime

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="app/templates")


# ── Login / Logout ───────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_side(request: Request):
    if request.session.get("admin"):
        return RedirectResponse(url="/admin/", status_code=303)
    return templates.TemplateResponse("admin/login.html", {"request": request, "fejl": False})


@router.post("/login")
async def login_handling(request: Request, adgangskode: str = Form(...)):
    if adgangskode == ADMIN_PASSWORD:
        request.session["admin"] = True
        return RedirectResponse(url="/admin/", status_code=303)
    return templates.TemplateResponse(
        "admin/login.html", {"request": request, "fejl": True}, status_code=401
    )


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/admin/login", status_code=303)


# ── Dashboard ────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    redirect = kræv_login(request)
    if redirect:
        return redirect

    i_dag = datetime.date.today()
    antal_bookinger = db.query(models.Booking).filter(
        models.Booking.check_out >= i_dag,
        models.Booking.status != models.BookingStatus.cancelled,
    ).count()
    antal_saesoner = db.query(models.SeasonInterval).count()
    antal_priser = db.query(models.SeasonPrice).count()

    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "aktiv_side": "dashboard",
        "antal_bookinger": antal_bookinger,
        "antal_saesoner": antal_saesoner,
        "antal_priser": antal_priser,
    })


# ── Sæsonintervaller ─────────────────────────────────────────────────────────

@router.get("/saesoner", response_class=HTMLResponse)
async def saesoner(request: Request, aar: int = None, db: Session = Depends(get_db)):
    redirect = kræv_login(request)
    if redirect:
        return redirect

    if aar is None:
        aar = datetime.date.today().year

    intervaller = db.query(models.SeasonInterval).order_by(
        models.SeasonInterval.date_from
    ).all()

    aarsoverblik = generer_aarsoverblik(aar, db)

    return templates.TemplateResponse("admin/saesoner.html", {
        "request": request,
        "aktiv_side": "saesoner",
        "intervaller": intervaller,
        "aarsoverblik": aarsoverblik,
        "aar": aar,
        "saeson_farver": SAESON_FARVER,
        "saeson_valg": ["A", "B", "C", "D", "E"],
    })


@router.post("/saesoner/opret")
async def opret_interval(
    request: Request,
    date_from: str = Form(...),
    date_to: str = Form(...),
    season: str = Form(...),
    label: str = Form(""),
    db: Session = Depends(get_db),
):
    redirect = kræv_login(request)
    if redirect:
        return redirect

    fra = datetime.date.fromisoformat(date_from)
    til = datetime.date.fromisoformat(date_to)

    nyt = models.SeasonInterval(
        date_from=fra,
        date_to=til,
        season=models.SeasonEnum(season),
        label=label.strip() or None,
    )
    db.add(nyt)
    db.commit()

    aar = fra.year
    return RedirectResponse(url=f"/admin/saesoner?aar={aar}", status_code=303)


@router.post("/saesoner/{interval_id}/slet")
async def slet_interval(
    request: Request,
    interval_id: int,
    db: Session = Depends(get_db),
):
    redirect = kræv_login(request)
    if redirect:
        return redirect

    interval = db.query(models.SeasonInterval).filter(
        models.SeasonInterval.id == interval_id
    ).first()
    if interval:
        db.delete(interval)
        db.commit()

    return RedirectResponse(url="/admin/saesoner", status_code=303)


# ── Sæsonpriser ──────────────────────────────────────────────────────────────

@router.get("/priser", response_class=HTMLResponse)
async def priser(request: Request, gemt: bool = False, db: Session = Depends(get_db)):
    redirect = kræv_login(request)
    if redirect:
        return redirect

    alle_priser = {p.season.value: p for p in db.query(models.SeasonPrice).all()}

    # Byg en liste med alle 5 sæsoner — uanset om prisen er sat eller ej
    saesoner = []
    for bogstav in ["A", "B", "C", "D", "E"]:
        pris = alle_priser.get(bogstav)
        saesoner.append({
            "bogstav": bogstav,
            "farve": SAESON_FARVER[bogstav],
            "price_per_week": pris.price_per_week if pris else "",
            "min_nights": pris.min_nights if pris else 7,
        })

    return templates.TemplateResponse("admin/priser.html", {
        "request": request,
        "aktiv_side": "priser",
        "saesoner": saesoner,
        "gemt": gemt,
    })


@router.post("/priser")
async def gem_priser(request: Request, db: Session = Depends(get_db)):
    redirect = kræv_login(request)
    if redirect:
        return redirect

    form = await request.form()

    for bogstav in ["A", "B", "C", "D", "E"]:
        pris_str = form.get(f"pris_{bogstav}", "").strip()
        min_str = form.get(f"min_{bogstav}", "7").strip()

        if not pris_str:
            continue  # Spring over tomme felter

        try:
            ugepris = Decimal(pris_str.replace(",", "."))
            min_nætter = int(min_str) if min_str else 7
        except (InvalidOperation, ValueError):
            continue

        eksisterende = db.query(models.SeasonPrice).filter(
            models.SeasonPrice.season == models.SeasonEnum(bogstav)
        ).first()

        if eksisterende:
            eksisterende.price_per_week = ugepris
            eksisterende.min_nights = min_nætter
        else:
            ny = models.SeasonPrice(
                season=models.SeasonEnum(bogstav),
                price_per_week=ugepris,
                min_nights=min_nætter,
            )
            db.add(ny)

    db.commit()
    return RedirectResponse(url="/admin/priser?gemt=1", status_code=303)


# ── Bookinger ────────────────────────────────────────────────────────────────

STATUS_LABELS = {
    "pending":   {"label": "Afventende", "bg": "bg-yellow-100", "text": "text-yellow-800"},
    "confirmed": {"label": "Bekræftet",  "bg": "bg-green-100",  "text": "text-green-800"},
    "cancelled": {"label": "Annulleret", "bg": "bg-gray-100",   "text": "text-gray-500"},
}


@router.get("/bookinger", response_class=HTMLResponse)
async def bookinger(
    request: Request,
    status: str = None,
    db: Session = Depends(get_db),
):
    redirect = kræv_login(request)
    if redirect:
        return redirect

    q = db.query(models.Booking)
    if status in ("pending", "confirmed", "cancelled"):
        q = q.filter(models.Booking.status == models.BookingStatus(status))
    q = q.order_by(models.Booking.check_in.asc())

    return templates.TemplateResponse("admin/bookinger.html", {
        "request": request,
        "aktiv_side": "bookinger",
        "bookinger": q.all(),
        "valgt_status": status,
        "status_labels": STATUS_LABELS,
    })


@router.get("/bookinger/opret", response_class=HTMLResponse)
async def opret_booking_side(request: Request):
    redirect = kræv_login(request)
    if redirect:
        return redirect
    return templates.TemplateResponse("admin/booking_opret.html", {
        "request": request,
        "aktiv_side": "bookinger",
        "fejl": None,
    })


@router.post("/bookinger/opret")
async def opret_booking_admin(
    request: Request,
    check_in: str = Form(...),
    check_out: str = Form(...),
    guest_name: str = Form(...),
    guest_email: str = Form(...),
    guest_phone: str = Form(""),
    guest_address: str = Form(""),
    guest_zip: str = Form(""),
    guest_city: str = Form(""),
    notes: str = Form(""),
    status: str = Form("confirmed"),
    db: Session = Depends(get_db),
):
    redirect = kræv_login(request)
    if redirect:
        return redirect

    from app.services.kalender import tjek_overlap
    from app.services.priser import beregn_pris

    fra = datetime.date.fromisoformat(check_in)
    til = datetime.date.fromisoformat(check_out)

    if tjek_overlap(fra, til, db):
        return templates.TemplateResponse("admin/booking_opret.html", {
            "request": request,
            "aktiv_side": "bookinger",
            "fejl": "Perioden overlapper med en eksisterende booking.",
            "check_in": check_in, "check_out": check_out,
            "guest_name": guest_name, "guest_email": guest_email,
            "guest_phone": guest_phone, "guest_address": guest_address,
            "guest_zip": guest_zip, "guest_city": guest_city, "notes": notes,
        })

    resultat = beregn_pris(fra, til, db)
    booking = models.Booking(
        guest_name=guest_name.strip(),
        guest_email=guest_email.strip(),
        guest_phone=guest_phone.strip(),
        guest_address=guest_address.strip() or None,
        guest_zip=guest_zip.strip() or None,
        guest_city=guest_city.strip() or None,
        check_in=fra,
        check_out=til,
        total_price=resultat["total"],
        status=models.BookingStatus(status),
        notes=notes.strip() or None,
    )
    db.add(booking)
    db.commit()
    return RedirectResponse(url="/admin/bookinger", status_code=303)


@router.get("/bookinger/{booking_id}", response_class=HTMLResponse)
async def booking_detalje(request: Request, booking_id: int, db: Session = Depends(get_db)):
    redirect = kræv_login(request)
    if redirect:
        return redirect

    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not booking:
        return RedirectResponse(url="/admin/bookinger", status_code=303)

    return templates.TemplateResponse("admin/booking_detalje.html", {
        "request": request,
        "aktiv_side": "bookinger",
        "booking": booking,
        "status_labels": STATUS_LABELS,
        "gemt": request.query_params.get("gemt"),
    })


@router.post("/bookinger/{booking_id}/opdater")
async def opdater_booking(
    request: Request,
    booking_id: int,
    status: str = Form(...),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    redirect = kræv_login(request)
    if redirect:
        return redirect

    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if booking:
        booking.status = models.BookingStatus(status)
        booking.notes  = notes.strip() or None
        db.commit()

    return RedirectResponse(url=f"/admin/bookinger/{booking_id}?gemt=1", status_code=303)


@router.post("/bookinger/{booking_id}/slet")
async def slet_booking(request: Request, booking_id: int, db: Session = Depends(get_db)):
    redirect = kræv_login(request)
    if redirect:
        return redirect

    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if booking:
        db.delete(booking)
        db.commit()

    return RedirectResponse(url="/admin/bookinger", status_code=303)


# ── Indstillinger ─────────────────────────────────────────────────────────────

@router.get("/indstillinger", response_class=HTMLResponse)
async def indstillinger_side(request: Request, db: Session = Depends(get_db)):
    redirect = kræv_login(request)
    if redirect:
        return redirect

    settings = db.query(models.Settings).filter(models.Settings.id == 1).first()
    if not settings:
        settings = models.Settings(id=1, electricity_price_kwh=Decimal("2.65"), water_price_m3=Decimal("65.00"))
        db.add(settings)
        db.commit()

    return templates.TemplateResponse("admin/indstillinger.html", {
        "request": request,
        "settings": settings,
        "gemt": request.query_params.get("gemt"),
    })


@router.post("/indstillinger")
async def gem_indstillinger(
    request: Request,
    admin_email: str = Form(""),
    electricity_price_kwh: str = Form("2.65"),
    water_price_m3: str = Form("65.00"),
    db: Session = Depends(get_db),
):
    redirect = kræv_login(request)
    if redirect:
        return redirect

    settings = db.query(models.Settings).filter(models.Settings.id == 1).first()
    if not settings:
        settings = models.Settings(id=1)
        db.add(settings)

    settings.admin_email = admin_email.strip() or None
    try:
        settings.electricity_price_kwh = Decimal(electricity_price_kwh.replace(",", "."))
    except InvalidOperation:
        settings.electricity_price_kwh = Decimal("2.65")
    try:
        settings.water_price_m3 = Decimal(water_price_m3.replace(",", "."))
    except InvalidOperation:
        settings.water_price_m3 = Decimal("65.00")

    db.commit()
    return RedirectResponse(url="/admin/indstillinger?gemt=1", status_code=303)
