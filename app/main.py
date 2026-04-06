from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import text
from app.database import engine, Base
from app.routers import public, admin
from dotenv import load_dotenv
import os

load_dotenv()

# Opret nye tabeller automatisk
try:
    Base.metadata.create_all(bind=engine)
except Exception:
    pass

# Tilføj nye kolonner hvis de ikke findes — kører uafhængigt af create_all
# Hver migration i sin egen forbindelse så PostgreSQL-fejl er isolerede
_MIGRATIONS = [
    "ALTER TABLE bookings ADD COLUMN guest_address VARCHAR(200)",
    "ALTER TABLE bookings ADD COLUMN guest_zip VARCHAR(10)",
    "ALTER TABLE bookings ADD COLUMN guest_city VARCHAR(100)",
    "ALTER TABLE bookings ADD COLUMN guest_remarks TEXT",
    "ALTER TABLE settings ADD COLUMN saturday_only INTEGER DEFAULT 1",
]
for _sql in _MIGRATIONS:
    try:
        with engine.connect() as _conn:
            _conn.execute(text(_sql))
            _conn.commit()
    except Exception:
        pass

app = FastAPI(title="iebeltoft.dk — Sommerhus Udlejning", docs_url=None, redoc_url=None)

app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "dev-secret-skift-mig"))

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(public.router)
app.include_router(admin.router)


@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    return {"status": "ok"}
