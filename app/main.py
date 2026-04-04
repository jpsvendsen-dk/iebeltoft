from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import text
from app.database import engine, Base
from app.routers import public, admin
from dotenv import load_dotenv
import os

load_dotenv()

# Opret nye tabeller automatisk (fejler lydløst hvis DB er i dvale ved opstart)
try:
    Base.metadata.create_all(bind=engine)

    # Tilføj nye Booking-kolonner hvis de ikke findes (kører ufarligt ved genstart)
    with engine.connect() as conn:
        for sql in [
            "ALTER TABLE bookings ADD COLUMN guest_address VARCHAR(200)",
            "ALTER TABLE bookings ADD COLUMN guest_zip VARCHAR(10)",
            "ALTER TABLE bookings ADD COLUMN guest_city VARCHAR(100)",
            "ALTER TABLE bookings ADD COLUMN guest_remarks TEXT",
        ]:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass
except Exception:
    pass

app = FastAPI(title="iebeltoft.dk — Sommerhus Udlejning", docs_url=None, redoc_url=None)

app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "dev-secret-skift-mig"))

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(public.router)
app.include_router(admin.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
