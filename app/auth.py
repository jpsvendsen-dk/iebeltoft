from fastapi import Request
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
import os

load_dotenv()

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "skift-mig")


def er_logget_ind(request: Request) -> bool:
    return request.session.get("admin") is True


def kræv_login(request: Request):
    """Returnerer redirect hvis ikke logget ind, ellers None."""
    if not er_logget_ind(request):
        return RedirectResponse(url="/admin/login", status_code=303)
    return None
