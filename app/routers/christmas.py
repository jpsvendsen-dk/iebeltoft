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
from app.services.calendar_client import client_metadata
from app.services.christmas_access import YEAR, TZ, today, available_day, allowed_day

router = APIRouter()
VERSION = "jul2026-2"

# Official Charts' top 24 most-streamed Christmas songs in the UK, reversed.
# Doors 2, 4, 11, 16 and 22 replaced with Danish songs at the owner's request.
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
    ("Jul Det' Cool", "MC Einar", "FuyKWtF5aqU"),
    ("Santa Tell Me", "Ariana Grande", "nlR0MkrRklg"),
    ("Do They Know It's Christmas?", "Band Aid", "RH-xd5bPKTA"),
    ("It's Beginning to Look a Lot Like Christmas", "Michael Bublé", "QJ5DOWPGxwg"),
    ("Rockin' Around the Christmas Tree", "Brenda Lee", "TFsZy9t-qDc"),
    ("Merry Christmas Everyone", "Shakin' Stevens", "N-PyWfVkjZc"),
    ("Jul i Angora", "Drengene Fra Angora", "SFpiOoWFNNg"),
    ("Last Christmas", "Wham!", "E8gmARGvPlI"),
    ("All I Want for Christmas Is You", "Mariah Carey", "aAkMkVFwAoo"),
]
ANIMALS = ["En ræv i den stille vinterskov", "En rødhals på en snedækket gren", "Et rådyr mellem grantræerne", "En hare i den bløde sne", "Et egern med en grankogle", "En ugle i vinterens skumring", "Et pindsvin ved en lille lanterne", "En grævling på en sneklædt sti", "En odder ved den frosne å", "En mus ved en rød svamp", "En kat i en sneklædt have", "En hund i den første sne", "En hest i vinterlandskabet", "Et får ved en gammel lade", "En ged under sneklædte grene", "En ko foran den lune stald", "En gås ved en vinterdam", "En and på den frosne sø", "En svane i snevejret", "En fasan i vintergræsset", "En dompap mellem røde bær", "En spætte i vinterskoven", "Et rensdyr under stjernerne", "En isbjørneunge i julesneen"]


REFLECTIONS = [
    "Send i tankerne en varm julehilsen til et menneske, du holder af, og mærk, hvad det vækker i dig.",
    "Lyt til sangen, og læg mærke til, hvilket decemberminde der dukker op, uden at lede efter et bestemt.",
    "Lad musikken tage dig på en lille tur, mens du mærker føddernes kontakt med gulvet.",
    "Tænk på et sted, hvor du kan være dig selv, og giv dig et øjeblik til at dvæle ved følelsen.",
    "Læg mærke til en lille ting omkring dig, som gør dig glad, og lad den få din fulde opmærksomhed.",
    "Mind dig selv om en kærlig gestus, du har modtaget, og læg mærke til, hvordan du husker den.",
    "Lad dette øjeblik være godt nok, uden at du behøver gøre det til noget særligt.",
    "Lad skuldrene synke lidt, og overvej, hvad du selv kan bidrage med af fred og venlighed i dag.",
    "Lyt efter et sted i musikken, der giver dig lyst til at smile eller bevæge dig, og følg gerne lysten.",
    "Mens du glæder dig til det, der kommer, så læg mærke til én god ting, der allerede er her.",
    "Forestil dig stille snefnug, der daler, og lad tankerne komme og gå i deres eget tempo.",
    "Giv plads til den december, du faktisk oplever, med både glæde, travlhed og alt det midt imellem.",
    "Lad tankerne finde hen til et menneske eller et sted, der giver dig en følelse af at høre til.",
    "Tænk på noget værdifuldt i dit liv, som aldrig har kunnet pakkes ind.",
    "Overvej, hvilken lille del af julens varme du kunne have lyst til at tage med ind i en almindelig hverdag.",
    "Mærk efter, hvad der betyder noget for dig i julen, når indkøbslisterne og forventningerne får lov at ligge lidt.",
    "Giv dig selv lov til ikke at kende alle svarene, og vend et øjeblik tilbage til musikken.",
    "Lad tankerne nå et menneske, der kunne bruge lidt omsorg, og overvej en lille, venlig handling.",
    "Se dig omkring med nysgerrighed, og opdag en farve, et lys eller en detalje, du ellers ville være gået forbi.",
    "Giv kroppen lov til at følge rytmen, også selvom det bare bliver til en vippende tå.",
    "Læg mærke til, hvordan et venligt blik eller et lille smil kan skabe kontakt mellem mennesker.",
    "Slip tanken om, hvordan julen burde se ud, og giv plads til det skæve, fjollede og uperfekte.",
    "Hvis sangen vækker savn eller gamle minder, så mød dem med samme venlighed, som du ville vise en god ven.",
    "Lad sangen minde dig om, hvem der betyder noget for dig, og giv også dig selv en kærlig tanke.",
]


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
    return {"day": day, "title": title, "artist": artist, "youtube": f"https://www.youtube.com/watch?v={video}", "animal": ANIMALS[day - 1], "reflection": REFLECTIONS[day - 1]}


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
    progress_version: StrictInt | None = Field(default=None, ge=0)


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
    if person:
        accounts.require_progress_version(db, person, body.progress_version)
    permitted = day <= allowed_day(today(), person, preview)
    if person:
        event_id = str(body.event_id)
        # The unique key makes retries safe across concurrent workers.
        inserted = db.execute(accounts.insert_for(db, CalendarDoorEvent).values(visitor_id=person.id, event_id=event_id, year=YEAR, day=day, clicked_at=accounts.utcnow(), result="opened" if permitted else "locked", progress_version=person.progress_version, **client_metadata(request)).on_conflict_do_nothing(index_elements=[CalendarDoorEvent.visitor_id, CalendarDoorEvent.event_id])).rowcount
        if inserted:
            if permitted:
                first_open = db.execute(accounts.insert_for(db, CalendarOpenedDoor).values(visitor_id=person.id, year=YEAR, day=day).on_conflict_do_nothing()).rowcount
                if not first_open:
                    db.execute(update(CalendarDoorEvent).where(CalendarDoorEvent.visitor_id == person.id, CalendarDoorEvent.event_id == event_id).values(result="reopened"))
        else:
            original = db.scalar(select(CalendarDoorEvent).where(CalendarDoorEvent.visitor_id == person.id, CalendarDoorEvent.event_id == event_id))
            if original.day != day or original.year != YEAR or original.progress_version != person.progress_version:
                db.rollback()
                raise HTTPException(409, "Dette tryk er allerede registreret for en anden låge.")
            # A retry never changes the original result or bypasses revoked access.
            permitted = permitted and original.result != "locked"
        db.commit()
    if not permitted:
        return locked_door(day)
    return JSONResponse(door_content(day), headers={"Cache-Control": "no-store"})
