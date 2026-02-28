from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from app.database import engine, Base
from app.routers import public, admin
from dotenv import load_dotenv
import os

load_dotenv()

# Opret tabeller automatisk (til lokal udvikling)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="iebeltoft.dk — Sommerhus Udlejning", docs_url=None, redoc_url=None)

app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "dev-secret-skift-mig"))

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(public.router)
app.include_router(admin.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
