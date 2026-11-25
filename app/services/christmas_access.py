from datetime import date, datetime
from zoneinfo import ZoneInfo

YEAR = 2026
TZ = ZoneInfo("Europe/Copenhagen")


def today():
    return datetime.now(TZ).date()


def available_day(current):
    return max(0, min(24, (current - date(YEAR, 12, 1)).days + 1))


def allowed_day(current, person=None, preview=False):
    return 24 if preview or (person is not None and person.early_access) else available_day(current)
