import datetime
import pathlib
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from app.services.kalender import generer_gaeste_kalender, tjek_overlap
from app.services.priser import beregn_pris
from app.services.saeson import SAESON_FARVER
from app.services.email import send_booking_notification
from app.utils import DANSKE_MAANEDER

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def forside(request: Request):
    return templates.TemplateResponse("public/forside.html", {"request": request})


@router.get("/booking", response_class=HTMLResponse)
async def booking_side(request: Request, db: Session = Depends(get_db)):
    maaneder = generer_gaeste_kalender(db)
    saeson_priser = db.query(models.SeasonPrice).order_by(models.SeasonPrice.season).all()
    settings = db.query(models.Settings).filter(models.Settings.id == 1).first()
    saturday_only = bool(settings and settings.saturday_only)
    return templates.TemplateResponse("public/booking.html", {
        "request": request,
        "maaneder": maaneder,
        "saeson_farver": SAESON_FARVER,
        "saeson_priser": saeson_priser,
        "settings": settings,
        "saturday_only": saturday_only,
        "fejl": request.query_params.get("fejl"),
    })


@router.get("/booking/pris", response_class=HTMLResponse)
async def pris_beregning(
    request: Request,
    check_in: str = None,
    check_out: str = None,
    db: Session = Depends(get_db),
):
    if not check_in or not check_out:
        return HTMLResponse("<p class='text-sm text-gray-400'>Vælg datoer for at se prisen.</p>")

    try:
        fra = datetime.date.fromisoformat(check_in)
        til = datetime.date.fromisoformat(check_out)
    except ValueError:
        return HTMLResponse("<p class='text-sm text-red-500'>Ugyldige datoer.</p>")

    if til <= fra:
        return HTMLResponse("<p class='text-sm text-red-500'>Afrejse skal være efter ankomst.</p>")

    resultat = beregn_pris(fra, til, db)

    return templates.TemplateResponse("public/partials/pris.html", {
        "request": request,
        "resultat": resultat,
        "fejl": resultat.get("fejl"),
    })


@router.post("/booking/opret")
async def opret_booking(
    request: Request,
    check_in: str = Form(...),
    check_out: str = Form(...),
    guest_name: str = Form(...),
    guest_email: str = Form(...),
    guest_phone: str = Form(...),
    guest_address: str = Form(...),
    guest_zip: str = Form(...),
    guest_city: str = Form(...),
    guest_remarks: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        fra = datetime.date.fromisoformat(check_in)
        til = datetime.date.fromisoformat(check_out)
    except ValueError:
        return RedirectResponse(url="/booking", status_code=303)

    if til <= fra or fra < datetime.date.today():
        return RedirectResponse(url="/booking", status_code=303)

    # Tjek lørdag-til-lørdag regel
    settings_check = db.query(models.Settings).filter(models.Settings.id == 1).first()
    if settings_check and settings_check.saturday_only:
        if fra.weekday() != 5 or til.weekday() != 5:  # 5 = lørdag
            return RedirectResponse(url="/booking?fejl=lordag", status_code=303)

    if tjek_overlap(fra, til, db):
        return RedirectResponse(url="/booking?fejl=optaget", status_code=303)

    resultat = beregn_pris(fra, til, db)

    booking = models.Booking(
        guest_name=guest_name.strip(),
        guest_email=guest_email.strip(),
        guest_phone=guest_phone.strip(),
        guest_address=guest_address.strip(),
        guest_zip=guest_zip.strip(),
        guest_city=guest_city.strip(),
        guest_remarks=guest_remarks.strip(),
        check_in=fra,
        check_out=til,
        total_price=resultat["total"],
        status=models.BookingStatus.pending,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)

    # Send notifikationsmail til admin
    settings = db.query(models.Settings).filter(models.Settings.id == 1).first()
    if settings and settings.admin_email:
        send_booking_notification(booking, settings.admin_email)

    return RedirectResponse(url=f"/booking/bekraeftelse/{booking.id}", status_code=303)


@router.get("/billeder", response_class=HTMLResponse)
async def billeder_side(request: Request):
    mappe = pathlib.Path("static/MoreImages")
    tilladte = {".jpg", ".jpeg", ".png"}
    billeder = []
    if mappe.exists():
        from PIL import Image, ExifTags
        for fil in sorted(mappe.iterdir()):
            if fil.suffix.lower() not in tilladte or fil.name.startswith("."):
                continue
            dato = None
            try:
                with Image.open(fil) as img:
                    exif = img._getexif()
                    if exif:
                        for tag_id, val in exif.items():
                            if ExifTags.TAGS.get(tag_id) == "DateTimeOriginal":
                                dato = datetime.datetime.strptime(val, "%Y:%m:%d %H:%M:%S").date()
                                break
            except Exception:
                pass
            if not dato:
                try:
                    dato = datetime.date.fromtimestamp(fil.stat().st_mtime)
                except Exception:
                    pass
            dato_str = ""
            if dato:
                dato_str = f"{dato.day}. {DANSKE_MAANEDER[dato.month]} {dato.year}"
            billeder.append({
                "filnavn": fil.name,
                "url": f"/static/MoreImages/{fil.name}",
                "dato": dato,
                "dato_str": dato_str,
            })
        billeder.sort(key=lambda b: b["dato"] or datetime.date.min, reverse=True)
    return templates.TemplateResponse("public/billeder.html", {
        "request": request,
        "billeder": billeder,
    })


@router.get("/booking/bekraeftelse/{booking_id}", response_class=HTMLResponse)
async def bekraeftelse(request: Request, booking_id: int, db: Session = Depends(get_db)):
    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not booking:
        return RedirectResponse(url="/booking", status_code=303)
    return templates.TemplateResponse("public/bekraeftelse.html", {
        "request": request,
        "booking": booking,
    })
