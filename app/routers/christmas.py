"""Christmas calendar. The server, never the visitor's clock, unlocks content."""
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, StrictInt, Field
from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import CalendarDoorEvent, CalendarOpenedDoor
from app.services import christmas_accounts as accounts
from app.services.christmas_access import YEAR, TZ, today, available_day, allowed_day

router = APIRouter()
VERSION = "jul2026-2"

# Official Charts' top 24 most-streamed Christmas songs in the UK, reversed.
# Doors 2, 4 and 11 replaced with Danish songs at the owner's request.
# Rank 9 is listed under Elton John's Christmas EP: Step Into Christmas.
SONGS = [
    ("Feliz Navidad", "José Feliciano", "N8NcQzMQN_U"),
    ("Der' noget i december", "Rasmus Seebach", "Mv6FViYatkU"),
    ("Sleigh Ride", "The Ronettes", "XZTzai1H9DM"),
    ("Tinka", "Burhan G & Frida Brygmann", "bjyw-jwPjoQ"),
    ("Holly Jolly Christmas", "Michael Bublé", "FXtPpXbrNkQ"),
    ("Mistletoe", "Justin Bieber", "LUjn3RpkcKY"),
    ("Wonderful Christmastime", "Paul McCartney", "94Ye-3C1FC8"),
    ("Happy Xmas (War Is Over)", "John Lennon & Yoko Ono", "flA5ndOyZbI"),
    ("Merry Xmas Everybody", "Slade", "PTslBTBl1X8"),
    ("One More Sleep", "Leona Lewis", "j-_1-uJ6Ml4"),
    ("I en stjerneregn af sne", "Mads Langer", "VxXW2aEWoJc"),
    ("It's the Most Wonderful Time of the Year", "Andy Williams", "AN_R4pR1hck"),
    ("Driving Home for Christmas", "Chris Rea", "DDt3u2Ev1cI"),
    ("Underneath the Tree", "Kelly Clarkson", "YfF10ow4YEo"),
    ("I Wish It Could Be Christmas Everyday", "Wizzard", "IJPc7esgvsA"),
    ("Step Into Christmas", "Elton John", "IbRtGMm96F8"),
    ("Santa Tell Me", "Ariana Grande", "nlR0MkrRklg"),
    ("Do They Know It's Christmas?", "Band Aid", "RH-xd5bPKTA"),
    ("It's Beginning to Look a Lot Like Christmas", "Michael Bublé", "QJ5DOWPGxwg"),
    ("Rockin' Around the Christmas Tree", "Brenda Lee", "TFsZy9t-qDc"),
    ("Merry Christmas Everyone", "Shakin' Stevens", "N-PyWfVkjZc"),
    ("Fairytale of New York", "The Pogues feat. Kirsty MacColl", "j9jbdgZidu8"),
    ("Last Christmas", "Wham!", "E8gmARGvPlI"),
    ("All I Want for Christmas Is You", "Mariah Carey", "aAkMkVFwAoo"),
]
ANIMALS = ["En ræv i den stille vinterskov", "En rødhals på en snedækket gren", "Et rådyr mellem grantræerne", "En hare i den bløde sne", "Et egern med en grankogle", "En ugle i vinterens skumring", "Et pindsvin ved en lille lanterne", "En grævling på en sneklædt sti", "En odder ved den frosne å", "En mus ved en rød svamp", "En kat i en sneklædt have", "En hund i den første sne", "En hest i vinterlandskabet", "Et får ved en gammel lade", "En ged under sneklædte grene", "En ko foran den lune stald", "En gås ved en vinterdam", "En and på den frosne sø", "En svane i snevejret", "En fasan i vintergræsset", "En dompap mellem røde bær", "En spætte i vinterskoven", "Et rensdyr under stjernerne", "En isbjørneunge i julesneen"]


def is_preview(request):
    preview = request.url.path.startswith("/admin/")
    if preview and request.session.get("admin") is not True:
        raise HTTPException(401, "Log ind som administrator for at se prøvelågerne.")
    return preview


@router.get("/Jul2026")
@router.get("/Jul2026/", include_in_schema=False)
@router.get("/admin/jul2026")
async def calendar(request: Request):
    if request.url.path.startswith("/admin/") and request.session.get("admin") is not True:
        return RedirectResponse("/admin/login", status_code=303)
    return FileResponse("static/jul2026/index.html", headers={"Cache-Control": "no-store"})


@router.get("/Jul2026/api/state")
@router.get("/admin/jul2026/api/state")
def state(request: Request, db: Session = Depends(get_db)):
    preview = is_preview(request)
    current = today()
    person = None if preview else accounts.visitor(request, db)
    return JSONResponse({"available": allowed_day(current, person, preview), "today": current.isoformat(), "year": YEAR, "preview": preview, "early_access": bool(person and person.early_access), "version": VERSION}, headers={"Cache-Control": "no-store"})


def door_content(day):
    title, artist, video = SONGS[day - 1]
    return {"day": day, "title": title, "artist": artist, "youtube": f"https://www.youtube.com/watch?v={video}", "animal": ANIMALS[day - 1]}


def locked_door(day):
    return JSONResponse({"detail": f"Lågen åbner den {day}. december 2026. Glæd dig!"}, status_code=403, headers={"Cache-Control": "no-store"})


@router.get("/Jul2026/api/doors/{day}")
@router.get("/admin/jul2026/api/doors/{day}")
def door(day: int, request: Request, db: Session = Depends(get_db)):
    preview = is_preview(request)
    if not 1 <= day <= 24:
        raise HTTPException(404, "Lågen findes ikke.")
    person = None if preview else accounts.visitor(request, db)
    if day > allowed_day(today(), person, preview):
        return locked_door(day)
    return JSONResponse(door_content(day), headers={"Cache-Control": "no-store"})


class DoorClick(BaseModel):
    event_id: UUID
    account_id: StrictInt | None = Field(default=None, gt=0)


@router.post("/Jul2026/api/doors/{day}/open")
@router.post("/admin/jul2026/api/doors/{day}/open")
def open_door(day: int, body: DoorClick, request: Request, db: Session = Depends(get_db)):
    accounts.require_same_origin(request)
    preview = is_preview(request)
    if not 1 <= day <= 24:
        raise HTTPException(404, "Lågen findes ikke.")
    person = None if preview else accounts.visitor(request, db)
    if not preview and body.account_id != (person.id if person else None):
        raise HTTPException(409 if person else 401, "Dit login er ændret. Opdatér kalenderen, og prøv igen.")
    permitted = day <= allowed_day(today(), person, preview)
    if person:
        event_id = str(body.event_id)
        # The unique key makes retries safe across concurrent workers.
        inserted = db.execute(accounts.insert_for(db, CalendarDoorEvent).values(visitor_id=person.id, event_id=event_id, year=YEAR, day=day, clicked_at=accounts.utcnow(), result="opened" if permitted else "locked").on_conflict_do_nothing(index_elements=[CalendarDoorEvent.visitor_id, CalendarDoorEvent.event_id])).rowcount
        if inserted:
            if permitted:
                first_open = db.execute(accounts.insert_for(db, CalendarOpenedDoor).values(visitor_id=person.id, year=YEAR, day=day).on_conflict_do_nothing()).rowcount
                if not first_open:
                    db.execute(update(CalendarDoorEvent).where(CalendarDoorEvent.visitor_id == person.id, CalendarDoorEvent.event_id == event_id).values(result="reopened"))
        else:
            original = db.scalar(select(CalendarDoorEvent).where(CalendarDoorEvent.visitor_id == person.id, CalendarDoorEvent.event_id == event_id))
            if original.day != day or original.year != YEAR:
                db.rollback()
                raise HTTPException(409, "Dette tryk er allerede registreret for en anden låge.")
            # A retry never changes the original result or bypasses revoked access.
            permitted = permitted and original.result != "locked"
        db.commit()
    if not permitted:
        return locked_door(day)
    return JSONResponse(door_content(day), headers={"Cache-Control": "no-store"})
