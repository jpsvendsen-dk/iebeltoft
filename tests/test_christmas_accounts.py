import os
import unittest
from datetime import date, timedelta
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware
from app.database import Base, get_db
from app.models import CalendarLoginLink, CalendarVisitor, CalendarLoginSession, CalendarOpenedDoor
from app.routers import christmas, christmas_accounts as routes
from app.services import christmas_accounts as accounts
from app.services.email import send_calendar_login

HEADERS = {"X-Calendar-Request": "1", "Origin": "https://testserver"}


class CalendarAccountTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.app = FastAPI()
        self.app.add_middleware(SessionMiddleware, secret_key="admin-test-only")
        self.app.include_router(christmas.router)
        self.app.include_router(routes.router)

        def db():
            with self.Session() as session:
                yield session

        self.app.dependency_overrides[get_db] = db
        self.client = self.device()
        self.mail = patch.object(routes, "send_calendar_login", return_value=True).start()
        patch.dict(os.environ, {"RESEND_API_KEY": "test-key", "CHRISTMAS_PUBLIC_URL": "https://calendar.example"}).start()
        self.now = accounts.utcnow()
        patch.object(accounts, "utcnow", side_effect=lambda: self.now).start()
        patch.object(routes, "today", return_value=date(2026, 12, 8)).start()

    def tearDown(self):
        patch.stopall()
        self.client.close()
        self.engine.dispose()

    def device(self):
        return TestClient(self.app, base_url="https://testserver")

    def request_link(self, email="friend@example.com", client=None):
        response = (client or self.client).post("/Jul2026/api/login/request", headers=HEADERS, json={"email": email})
        self.assertEqual(response.status_code, 200, response.text)
        url = self.mail.call_args.args[1]
        self.assertTrue(url.startswith("https://calendar.example/Jul2026/login#token="))
        return parse_qs(urlsplit(url).fragment)["token"][0]

    def login(self, email="friend@example.com", client=None):
        client = client or self.client
        token = self.request_link(email, client)
        response = client.post("/Jul2026/api/login/consume", headers=HEADERS, json={"token": token})
        self.assertEqual(response.status_code, 200, response.text)
        return client.get("/Jul2026/api/account").json()["account"]

    def save(self, client, account_id, days):
        return client.post("/Jul2026/api/account/opened", headers=HEADERS, json={"account_id": account_id, "days": days})

    def test_link_is_hashed_one_use_and_scanner_safe(self):
        token = self.request_link(" Friend@Example.com ")
        with self.Session() as db:
            row = db.scalar(select(CalendarLoginLink))
            self.assertEqual(row.token_hash, accounts.digest(token))
            self.assertEqual(row.email, "friend@example.com")
            self.assertIsNone(row.used_at)
        page = self.client.get("/Jul2026/login")
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.headers["referrer-policy"], "no-referrer")
        with self.Session() as db:
            self.assertIsNone(db.scalar(select(CalendarLoginLink)).used_at)
        response = self.client.post("/Jul2026/api/login/consume", headers=HEADERS, json={"token": token})
        self.assertEqual(response.status_code, 200)
        cookie = response.headers["set-cookie"]
        for attribute in ("HttpOnly", "Secure", "SameSite=lax", "Max-Age=7776000", "Path=/Jul2026"):
            self.assertIn(attribute, cookie)
        replay = self.device().post("/Jul2026/api/login/consume", headers=HEADERS, json={"token": token})
        self.assertEqual(replay.status_code, 400)
        self.assertEqual(self.client.get("/admin/jul2026/api/state").status_code, 401)
        with self.Session() as db:
            session = db.scalar(select(CalendarLoginSession))
            self.assertNotEqual(session.token_hash, self.client.cookies.get(accounts.COOKIE))

    def test_two_devices_merge_and_other_people_stay_separate(self):
        first = self.login()
        self.assertEqual(self.save(self.client, first["id"], [1, 2]).json()["opened"], [1, 2])
        self.now += timedelta(minutes=2)
        other_device = self.device()
        second = self.login("FRIEND@example.com", other_device)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(second["opened"], [1, 2])
        self.assertEqual(self.save(other_device, second["id"], [2, 3]).json()["opened"], [1, 2, 3])
        self.assertEqual(self.save(self.client, first["id"], [1, 4, 4]).json()["opened"], [1, 2, 3, 4])
        self.assertEqual(other_device.get("/Jul2026/api/account").json()["account"]["opened"], [1, 2, 3, 4])
        stranger = self.device()
        third = self.login("someone@example.com", stranger)
        self.assertEqual(third["opened"], [])
        self.assertEqual(self.save(stranger, first["id"], [1]).status_code, 409)
        self.assertEqual(self.save(stranger, third["id"], [5]).json()["opened"], [5])
        self.assertEqual(self.client.get("/Jul2026/api/account").json()["account"]["opened"], [1, 2, 3, 4])

    def test_future_and_invalid_doors_never_save(self):
        person = self.login()
        for days in ([9], [0], [25], [-1], [True], ["2"], [1] * 25):
            self.assertEqual(self.save(self.client, person["id"], days).status_code, 422)
        self.assertEqual(self.client.get("/Jul2026/api/account").json()["account"]["opened"], [])
        self.assertEqual(self.save(self.device(), person["id"], [1]).status_code, 401)

    def test_expiry_and_logout_only_current_device(self):
        token = self.request_link()
        self.now += timedelta(minutes=16)
        self.assertEqual(self.client.post("/Jul2026/api/login/consume", headers=HEADERS, json={"token": token}).status_code, 400)
        first = self.login()
        self.save(self.client, first["id"], [1])
        self.now += timedelta(minutes=2)
        other = self.device()
        self.login(client=other)
        stale_cookie = self.client.cookies.get(accounts.COOKIE)
        self.assertEqual(self.client.post("/Jul2026/api/logout", headers=HEADERS).status_code, 200)
        self.assertIsNone(self.client.get("/Jul2026/api/account").json()["account"])
        self.assertEqual(other.get("/Jul2026/api/account").json()["account"]["opened"], [1])
        replay = self.device()
        replay.cookies.set(accounts.COOKIE, stale_cookie)
        self.assertIsNone(replay.get("/Jul2026/api/account").json()["account"])
        self.now += timedelta(days=91)
        self.assertIsNone(other.get("/Jul2026/api/account").json()["account"])

    def test_origin_validation_and_no_host_poisoning(self):
        for headers in ({}, {**HEADERS, "Origin": "https://evil.example"}):
            self.assertEqual(self.client.post("/Jul2026/api/login/request", headers=headers, json={"email": "friend@example.com"}).status_code, 403)
        bad_host = self.device()
        response = bad_host.post("/Jul2026/api/login/request", headers={**HEADERS, "Host": "attacker.example", "Origin": "https://attacker.example"}, json={"email": "friend@example.com"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.mail.call_args.args[1].startswith("https://calendar.example/"))
        self.assertNotIn("token", self.client.get("/Jul2026/api/account").text)
        self.assertEqual(self.client.get("/Jul2026/api/account").headers["cache-control"], "no-store")

    def test_email_validation_and_rate_limits(self):
        for email in ("no-email", "a\r\nb@example.com", "a..b@example.com", ".a@example.com", "a@example..com"):
            self.assertEqual(self.client.post("/Jul2026/api/login/request", headers=HEADERS, json={"email": email}).status_code, 422)
        self.request_link()
        self.assertEqual(self.client.post("/Jul2026/api/login/request", headers=HEADERS, json={"email": "FRIEND@example.com"}).status_code, 429)
        for i in range(19):
            self.request_link(f"friend{i}@example.com")
        self.assertEqual(self.client.post("/Jul2026/api/login/request", headers=HEADERS, json={"email": "extra@example.com"}).status_code, 429)
        self.assertEqual(self.mail.call_count, 20)

    def test_mail_failure_invalidates_link_and_missing_configuration(self):
        self.mail.return_value = False
        response = self.client.post("/Jul2026/api/login/request", headers=HEADERS, json={"email": "friend@example.com"})
        self.assertEqual(response.status_code, 503)
        with self.Session() as db:
            self.assertIsNone(db.scalar(select(CalendarLoginLink)))
            self.assertIsNone(db.scalar(select(CalendarVisitor)))
        with patch.dict(os.environ, {"RESEND_API_KEY": ""}):
            self.assertEqual(self.client.post("/Jul2026/api/login/request", headers=HEADERS, json={"email": "other@example.com"}).status_code, 503)
        with patch.dict(os.environ, {"CHRISTMAS_PUBLIC_URL": "http://attacker.example"}):
            self.assertEqual(self.client.post("/Jul2026/api/login/request", headers=HEADERS, json={"email": "other@example.com"}).status_code, 503)

    def test_email_payload_contains_link_without_logging_it(self):
        with patch("app.services.email.httpx.post") as post:
            post.return_value.status_code = 200
            self.assertTrue(send_calendar_login("friend@example.com", "https://calendar.example/Jul2026/login#token=secret"))
            payload = post.call_args.kwargs["json"]
            self.assertEqual(payload["to"], ["friend@example.com"])
            self.assertIn("#token=secret", payload["text"])
            self.assertIn("15 minutter", payload["html"])
            post.return_value.status_code = 403
            self.assertFalse(send_calendar_login("friend@example.com", "https://calendar.example/Jul2026/login#token=secret"))


if __name__ == "__main__":
    unittest.main()
