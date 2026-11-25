import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware
from app.routers import christmas


class ChristmasTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.add_middleware(SessionMiddleware, secret_key="test-only")
        app.include_router(christmas.router)

        @app.get("/test-login")
        def login(request: christmas.Request):
            request.session["admin"] = True
            return {"ok": True}

        self.client = TestClient(app)

    def test_date_boundaries(self):
        for current, expected in [(date(2026, 11, 30), 0), (date(2026, 12, 1), 1), (date(2026, 12, 23), 23), (date(2026, 12, 24), 24), (date(2027, 1, 1), 24)]:
            self.assertEqual(christmas.available_day(current), expected)
        self.assertEqual(datetime(2026, 11, 30, 23, tzinfo=timezone.utc).astimezone(christmas.TZ).date(), date(2026, 12, 1))

    def test_every_door_across_december(self):
        for available in range(25):
            current = date(2026, 11, 30) if available == 0 else date(2026, 12, available)
            with patch.object(christmas, "today", return_value=current):
                state = self.client.get("/Jul2026/api/state")
                self.assertEqual(state.json()["available"], available)
                self.assertEqual(state.headers["cache-control"], "no-store")
                for day in range(1, 25):
                    response = self.client.get(f"/Jul2026/api/doors/{day}")
                    self.assertEqual(response.status_code, 200 if day <= available else 403)
                    self.assertEqual(response.headers["cache-control"], "no-store")
                    if day > available:
                        self.assertNotIn("youtube", response.json())
                        self.assertNotIn("title", response.json())
                        self.assertNotIn("reflection", response.json())
                    else:
                        self.assertEqual(response.json()["reflection"], christmas.REFLECTIONS[day - 1])

    def test_public_cannot_enable_preview(self):
        with patch.object(christmas, "today", return_value=date(2026, 11, 24)):
            self.assertEqual(self.client.get("/Jul2026/api/state?preview=1&date=2026-12-24").json()["available"], 0)
            self.assertEqual(self.client.get("/Jul2026/api/doors/24?preview=1").status_code, 403)
        self.assertEqual(self.client.get("/admin/jul2026", follow_redirects=False).status_code, 303)
        self.assertEqual(self.client.get("/admin/jul2026/api/state").status_code, 401)
        self.assertEqual(self.client.get("/admin/jul2026/api/doors/24").status_code, 401)

    def test_authenticated_preview_and_christmas_eve(self):
        self.client.get("/test-login")
        with patch.object(christmas, "today", return_value=date(2026, 11, 24)):
            self.assertEqual(self.client.get("/admin/jul2026/api/state").json()["available"], 24)
            for day in range(1, 25):
                response = self.client.get(f"/admin/jul2026/api/doors/{day}")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["reflection"], christmas.REFLECTIONS[day - 1])
        data = self.client.get("/admin/jul2026/api/doors/24").json()
        self.assertEqual(data["artist"], "Mariah Carey")
        for day in (0, 25, -1):
            self.assertEqual(self.client.get(f"/Jul2026/api/doors/{day}").status_code, 404)

    def test_page_contains_no_future_songs(self):
        response = self.client.get("/Jul2026")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("aAkMkVFwAoo", response.text)
        self.assertEqual(len(christmas.SONGS), 24)
        self.assertEqual(len(christmas.ANIMALS), 24)
        self.assertEqual(len(christmas.REFLECTIONS), 24)
        self.assertEqual(len(set(christmas.REFLECTIONS)), 24)
        for reflection in christmas.REFLECTIONS:
            self.assertNotIn(reflection, response.text)


if __name__ == "__main__":
    unittest.main()
