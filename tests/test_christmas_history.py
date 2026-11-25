import re
import unittest
import ast
from pathlib import Path
from datetime import date, datetime, timedelta
from uuid import uuid4
from unittest.mock import patch
from fastapi import Request
from sqlalchemy import select, create_engine
from app.models import CalendarVisitor, CalendarDoorEvent, CalendarLoginEvent
from app.routers import christmas, christmas_admin
import test_christmas_accounts as account_tests

HEADERS = account_tests.HEADERS


class CalendarHistoryTests(unittest.TestCase):
    def test_profile_table_sorting_names_and_latest_log(self):
        from app.models import CalendarSnakeEvent, CalendarSnakeProfile
        with self.Session() as db:
            people = [CalendarVisitor(email=f'{name}@example.com',early_access=i==1) for i,name in enumerate(('alpha','beta','gamma'))]
            db.add_all(people);db.flush()
            ids=[p.id for p in people]
            db.add_all([CalendarSnakeProfile(visitor_id=ids[0],year=2026,display_name='Zebra'),CalendarSnakeProfile(visitor_id=ids[1],year=2026,display_name='Alf')])
            for i in range(2):
                db.add(CalendarLoginEvent(visitor_id=ids[0],year=2026,logged_at=self.now+timedelta(minutes=i)))
            db.add(CalendarLoginEvent(visitor_id=ids[1],year=2026,logged_at=self.now))
            db.add(CalendarDoorEvent(visitor_id=ids[1],year=2026,event_id=str(uuid4()),day=1,result='opened',clicked_at=self.now+timedelta(minutes=2)))
            db.add(CalendarSnakeEvent(id=str(uuid4()),visitor_id=ids[0],year=2026,action='open',clicked_at=self.now+timedelta(minutes=3)))
            db.add(CalendarSnakeEvent(id=str(uuid4()),visitor_id=ids[1],year=2025,action='open',clicked_at=self.now+timedelta(days=1)))
            db.commit()
        admin,_=self.admin()
        path='/admin/jul2026/indstillinger'
        expected={'email':ids,'name':[ids[1],ids[0],ids[2]],'login':[ids[2],ids[1],ids[0]],'doors':[ids[0],ids[2],ids[1]],'snake':[ids[1],ids[2],ids[0]],'last_log':[ids[1],ids[0],ids[2]],'early_access':[ids[0],ids[2],ids[1]]}
        for key,order in expected.items():
            page=admin.get(path,params={'sort':key})
            self.assertEqual([p.id for p in page.context['people']],order,key)
        page=admin.get(path,params={'sort':'last_log','direction':'desc'})
        self.assertEqual([p.id for p in page.context['people']],[ids[0],ids[1],ids[2]])
        self.assertEqual(page.context['last_logs'][ids[0]],'08.12.2026 kl. 12:37:56')
        self.assertIsNone(page.context['last_logs'][ids[2]])
        self.assertIn('aria-sort="descending"',page.text)
        self.assertIn('Ingen log',page.text)
        self.assertEqual(admin.get(path,params={'q':'zEbRa'}).context['total'],1)
        self.assertEqual(admin.get(path,params={'q':'%'}).context['total'],0)
        self.assertEqual(admin.get(path,params={'sort':'invalid'}).status_code,422)

    def test_profile_table_sorts_before_pagination_and_keeps_filters(self):
        from app.models import CalendarSnakeProfile
        with self.Session() as db:
            for i in range(52):
                person=CalendarVisitor(email=f'player{i:02}@example.com');db.add(person);db.flush()
                db.add(CalendarSnakeProfile(visitor_id=person.id,year=2026,display_name=f'Nisse {51-i:02}'))
            db.commit()
        admin,_=self.admin()
        first=admin.get('/admin/jul2026/indstillinger',params={'q':'player','sort':'name','direction':'desc'})
        self.assertEqual(first.context['people'][0].email,'player00@example.com')
        self.assertTrue(first.context['has_next'])
        self.assertIn('sort=name&amp;direction=desc&amp;page=2',first.text)
        second=admin.get('/admin/jul2026/indstillinger',params={'q':'player','sort':'name','direction':'desc','page':2})
        self.assertEqual([p.email for p in second.context['people']],['player50@example.com','player51@example.com'])

    def test_snake_history_guest_filter_counts_and_deletion(self):
        from app.models import CalendarSnakeEvent, CalendarSnakeProfile
        person=self.login()
        self.save(self.client,person['id'],[2])
        with self.Session() as db:
            for action in ('open','replay'):
                db.add(CalendarSnakeEvent(id=str(uuid4()),visitor_id=person['id'],year=2026,action=action,clicked_at=self.now,ip_address='203.0.113.8',device_type='iPhone'))
            db.add(CalendarSnakeEvent(id=str(uuid4()),year=2026,action='open',clicked_at=self.now))
            db.add(CalendarSnakeProfile(visitor_id=person['id'],year=2026,best_score=80))
            db.commit()
        self.assertEqual(self.client.get('/admin/jul2026/historik?kind=snake',follow_redirects=False).status_code,303)
        admin,csrf=self.admin()
        page=admin.get('/admin/jul2026/historik?kind=snake')
        self.assertEqual(page.status_code,200)
        self.assertEqual(len(page.context['events']),3)
        self.assertTrue(any(e['email']=='Gæst (uden login)' for e in page.context['events']))
        filtered=admin.get('/admin/jul2026/historik',params={'kind':'snake','email':person['email'],'day':'24'})
        self.assertEqual(len(filtered.context['events']),2)
        self.assertEqual({e['result'] for e in filtered.context['events']},{'Spil Jule-Snake','Spil igen'})
        self.assertEqual(admin.get('/admin/jul2026/indstillinger').context['snake_counts'][person['id']],2)
        path=f"/admin/jul2026/historik/slet?person_id={person['id']}"
        self.assertEqual(admin.get(path).context['counts']['snake'],2)
        admin.post(path,data={'csrf':csrf,'confirm':'delete-history'})
        self.assertEqual(len(admin.get('/admin/jul2026/historik?kind=snake').context['events']),1)
        with self.Session() as db:
            self.assertEqual(db.get(CalendarSnakeProfile,(person['id'],2026)).best_score,80)
        self.assertEqual(self.client.get('/Jul2026/api/account').json()['account']['opened'],[2])
        admin.post('/admin/jul2026/historik/slet',data={'csrf':csrf,'confirm':'delete-history'})
        self.assertEqual(admin.get('/admin/jul2026/historik?kind=snake').context['events'],[])

    device = account_tests.CalendarAccountTests.device
    request_link = account_tests.CalendarAccountTests.request_link
    login = account_tests.CalendarAccountTests.login
    save = account_tests.CalendarAccountTests.save
    tearDown = account_tests.CalendarAccountTests.tearDown

    def setUp(self):
        account_tests.CalendarAccountTests.setUp(self)
        self.app.include_router(christmas_admin.router)

        @self.app.get("/test-admin-login")
        def admin_login(request: Request):
            request.session["admin"] = True
            return {"ok": True}

        patch.object(christmas, "today", return_value=date(2026, 12, 8)).start()
        self.now = datetime(2026, 12, 8, 11, 34, 56)

    def click(self, day, person=None, client=None, event_id=None):
        return (client or self.client).post(f"/Jul2026/api/doors/{day}/open", headers=HEADERS, json={"event_id": event_id or str(uuid4()), "account_id": person["id"] if person else None, "clicked_at": "1900-01-01T00:00:00Z"})

    def events(self):
        with self.Session() as db:
            return db.scalars(select(CalendarDoorEvent).order_by(CalendarDoorEvent.id)).all()

    def admin(self):
        client = self.device()
        client.get("/test-admin-login")
        response = client.get("/admin/jul2026/indstillinger")
        self.assertEqual(response.status_code, 200)
        token = re.search(r'name="csrf" value="([^"]+)"', response.text).group(1)
        return client, token

    def access(self, client, token, person, enabled):
        return client.post(f"/admin/jul2026/indstillinger/brugere/{person['id']}", data={"csrf": token, "early_access": str(enabled).lower()}, follow_redirects=False)

    def test_each_click_logs_server_time_and_sync_is_not_a_click(self):
        person = self.login()
        self.assertEqual(self.click(2, person).status_code, 200)
        self.now += timedelta(seconds=10)
        self.assertEqual(self.click(2, person).status_code, 200)
        self.assertEqual(self.click(24, person).status_code, 403)
        events = self.events()
        self.assertEqual([e.result for e in events], ["opened", "reopened", "locked"])
        self.assertEqual([e.day for e in events], [2, 2, 24])
        self.assertEqual(events[0].clicked_at, datetime(2026, 12, 8, 11, 34, 56))
        self.assertEqual(events[0].visitor_id, person["id"])
        self.assertEqual(self.client.get("/Jul2026/api/doors/2").status_code, 200)
        self.assertEqual(self.save(self.client, person["id"], [1, 2]).status_code, 200)
        self.assertEqual(len(self.events()), 3)
        self.assertEqual(self.client.get("/Jul2026/api/account").json()["account"]["opened"], [1, 2])

    def test_idempotency_and_no_bypass_after_permission_changes(self):
        person = self.login()
        event = str(uuid4())
        self.assertEqual(self.click(2, person, event_id=event).status_code, 200)
        self.assertEqual(self.click(2, person, event_id=event).status_code, 200)
        self.assertEqual(len(self.events()), 1)
        self.assertEqual(self.click(3, person, event_id=event).status_code, 409)
        locked_id = str(uuid4())
        self.assertEqual(self.click(24, person, event_id=locked_id).status_code, 403)
        self.assertEqual(self.click(24, person, event_id=locked_id).status_code, 403)
        admin, csrf = self.admin()
        self.assertEqual(self.access(admin, csrf, person, True).status_code, 303)
        self.assertEqual(self.click(24, person, event_id=locked_id).status_code, 403)
        opened_id = str(uuid4())
        self.assertEqual(self.click(24, person, event_id=opened_id).status_code, 200)
        self.access(admin, csrf, person, False)
        self.assertEqual(self.click(24, person, event_id=opened_id).status_code, 403)
        self.assertEqual(len(self.events()), 3)

    def test_admin_can_pregrant_profile_without_sending_mail(self):
        admin, csrf = self.admin()
        response = admin.post("/admin/jul2026/indstillinger/tilfoej", data={"csrf": csrf, "email": "EARLY@example.com", "early_access": "true"}, follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.mail.call_count, 0)
        person = self.login("early@example.com")
        self.assertTrue(person["early_access"])
        self.assertEqual(self.client.get("/Jul2026/api/state").json()["available"], 24)
        self.assertEqual(self.click(24, person).status_code, 200)
        other = self.device()
        ordinary = self.login("other@example.com", other)
        self.assertEqual(other.get("/Jul2026/api/state").json()["available"], 8)
        self.assertEqual(self.click(24, ordinary, other).status_code, 403)
        # Adding an existing address must never overwrite that person's access.
        admin.post("/admin/jul2026/indstillinger/tilfoej", data={"csrf": csrf, "email": "early@example.com"})
        self.assertTrue(self.client.get("/Jul2026/api/account").json()["account"]["early_access"])

    def test_revoking_access_keeps_progress_across_devices(self):
        person = self.login()
        admin, csrf = self.admin()
        self.access(admin, csrf, person, True)
        self.assertEqual(self.click(24, person).status_code, 200)
        self.now += timedelta(minutes=2)
        second = self.device()
        profile = self.login(client=second)
        self.assertEqual(profile["opened"], [24])
        self.assertEqual(second.get("/Jul2026/api/state").json()["available"], 24)
        self.access(admin, csrf, person, False)
        for client in (self.client, second):
            self.assertEqual(client.get("/Jul2026/api/state").json()["available"], 8)
            self.assertIn(24, client.get("/Jul2026/api/account").json()["account"]["opened"])
            self.assertEqual(client.get("/Jul2026/api/doors/24").status_code, 403)
            self.assertEqual(self.save(client, person["id"], [1, 24]).status_code, 200)
            self.assertEqual(self.save(client, person["id"], [23, 24]).status_code, 422)

    def test_guest_and_admin_preview_do_not_create_user_events(self):
        self.assertEqual(self.click(2).status_code, 200)
        self.assertEqual(self.click(24).status_code, 403)
        admin, _ = self.admin()
        response = admin.post("/admin/jul2026/api/doors/24/open", headers=HEADERS, json={"event_id": str(uuid4()), "account_id": None})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.events(), [])
        self.assertEqual(self.client.post("/admin/jul2026/api/doors/24/open", headers=HEADERS, json={"event_id": str(uuid4())}).status_code, 401)

    def test_public_cannot_read_history_or_change_access(self):
        person = self.login()
        admin, token = self.admin()
        for path in ("/admin/jul2026/indstillinger", "/admin/jul2026/historik"):
            self.assertEqual(self.client.get(path, follow_redirects=False).status_code, 303)
        self.assertEqual(self.access(self.client, token, person, True).status_code, 401)
        self.assertEqual(self.access(admin, "wrong-token", person, True).status_code, 403)
        self.assertEqual(admin.post(f"/admin/jul2026/indstillinger/brugere/{person['id']}", data={"early_access": "true"}).status_code, 422)
        self.assertFalse(self.client.get("/Jul2026/api/account").json()["account"]["early_access"])
        self.assertEqual(self.click(1, {"id": person["id"] + 1}).status_code, 409)
        self.assertEqual(self.client.post("/Jul2026/api/doors/1/open", json={"event_id": str(uuid4()), "account_id": person["id"]}).status_code, 403)
        self.assertEqual(self.events(), [])

    def test_history_has_danish_time_filters_and_pagination(self):
        person = self.login("tag+one@example.com")
        self.click(2, person)
        self.now = datetime(2026, 7, 1, 10, 0, 0)
        self.click(3, person)
        admin, _ = self.admin()
        history = admin.get("/admin/jul2026/historik")
        self.assertIn("08.12.2026 kl. 12:34:56 CET", history.text)
        self.assertIn("01.07.2026 kl. 12:00:00 CEST", history.text)
        self.assertEqual(history.headers["cache-control"], "no-store")
        filtered = admin.get("/admin/jul2026/historik", params={"email": person["email"], "day": "3"})
        self.assertIn("1 hændelser", filtered.text)
        self.assertNotIn("08.12.2026 kl.", filtered.text)
        self.assertEqual(admin.get("/admin/jul2026/historik?day=").status_code, 200)
        self.assertEqual(admin.get("/admin/jul2026/historik?day=25").status_code, 422)
        self.assertIn("Ingen hændelser fundet", admin.get("/admin/jul2026/historik?email=absent@example.com").text)
        with self.Session() as db:
            for _ in range(50):
                db.add(CalendarDoorEvent(visitor_id=person["id"], event_id=str(uuid4()), year=2026, day=1, clicked_at=self.now, result="reopened"))
            db.commit()
        first = admin.get("/admin/jul2026/historik")
        second = admin.get("/admin/jul2026/historik?page=2")
        self.assertEqual(first.text.count("<time "), 50)
        self.assertEqual(second.text.count("<time "), 2)
        self.assertIn("Næste side", first.text)
        self.assertIn("Forrige side", second.text)

    def test_door_input_validation(self):
        person = self.login()
        for day in (0, 25):
            self.assertEqual(self.click(day, person).status_code, 404)
        self.assertEqual(self.click(1, person, event_id="invalid").status_code, 422)
        self.assertEqual(self.events(), [])

    def test_delete_history_per_user_then_all_preserves_accounts_and_progress(self):
        first = self.login()
        self.click(2, first)
        self.now += timedelta(minutes=2)
        second_client = self.device()
        second = self.login('other@example.com', second_client)
        self.click(3, second, second_client)
        admin, csrf = self.admin()
        self.access(admin, csrf, first, True)
        path = f"/admin/jul2026/historik/slet?person_id={first['id']}"
        confirmation = admin.get(path)
        self.assertEqual(confirmation.status_code, 200)
        self.assertEqual(confirmation.context['counts'], {'login': 1, 'doors': 1, 'snake': 0})
        self.assertEqual(len(self.events()), 2)  # GET never deletes.
        self.assertEqual(admin.post(path, data={'csrf': csrf, 'confirm': 'delete-history'}, follow_redirects=False).status_code, 303)
        self.assertEqual([event.visitor_id for event in self.events()], [second['id']])
        with self.Session() as db:
            self.assertEqual([event.visitor_id for event in db.scalars(select(CalendarLoginEvent))], [second['id']])
        profile = self.client.get('/Jul2026/api/account').json()['account']
        self.assertEqual(profile['opened'], [2])
        self.assertEqual(profile['progress_version'], 0)
        self.assertTrue(profile['early_access'])
        settings = admin.get('/admin/jul2026/indstillinger')
        self.assertNotIn(first['id'], settings.context['door_counts'])
        self.assertNotIn(first['id'], settings.context['login_counts'])
        self.assertEqual(settings.context['door_counts'][second['id']], 1)
        all_path = '/admin/jul2026/historik/slet'
        self.assertIsNone(admin.get(all_path).context['person'])
        self.assertEqual(admin.post(all_path, data={'csrf': csrf, 'confirm': 'delete-history'}, follow_redirects=False).status_code, 303)
        self.assertEqual(self.events(), [])
        with self.Session() as db:
            self.assertEqual(db.scalars(select(CalendarLoginEvent)).all(), [])
        self.assertEqual(second_client.get('/Jul2026/api/account').json()['account']['opened'], [3])
        self.click(2, first)
        self.assertEqual(self.events()[0].result, 'reopened')
        self.now += timedelta(minutes=2)
        self.login()
        self.assertEqual(admin.get('/admin/jul2026/indstillinger').context['login_counts'][first['id']], 1)

    def test_delete_history_requires_admin_csrf_confirmation_and_existing_user(self):
        person = self.login()
        self.click(1, person)
        admin, csrf = self.admin()
        for path in ('/admin/jul2026/historik/slet', f"/admin/jul2026/historik/slet?person_id={person['id']}"):
            self.assertEqual(self.client.get(path, follow_redirects=False).status_code, 303)
            self.assertEqual(self.client.post(path, data={'csrf': csrf, 'confirm': 'delete-history'}).status_code, 401)
            self.assertEqual(admin.post(path, data={'csrf': 'wrong', 'confirm': 'delete-history'}).status_code, 403)
            self.assertEqual(admin.post(path, data={'csrf': csrf, 'confirm': 'wrong'}).status_code, 400)
            self.assertEqual(admin.post(path, data={'csrf': csrf}).status_code, 422)
        missing = '/admin/jul2026/historik/slet?person_id=999999'
        self.assertEqual(admin.get(missing).status_code, 404)
        self.assertEqual(admin.post(missing, data={'csrf': csrf, 'confirm': 'delete-history'}).status_code, 404)
        self.assertEqual(admin.get('/admin/jul2026/historik/slet?person_id=0').status_code, 422)
        self.assertEqual(len(self.events()), 1)

    def test_reset_preserves_history_access_and_invalidates_old_devices(self):
        person = self.login()
        admin, csrf = self.admin()
        self.access(admin, csrf, person, True)
        event_id = str(uuid4())
        self.click(24, person, event_id=event_id)
        self.now += timedelta(minutes=2)
        second = self.device()
        self.login(client=second)
        path = f"/admin/jul2026/indstillinger/brugere/{person['id']}/nulstil"
        self.assertEqual(self.client.get(path, follow_redirects=False).status_code, 303)
        self.assertEqual(admin.get(path).status_code, 200)
        self.assertEqual(admin.post(path, data={"csrf": "bad", "confirm": "reset"}).status_code, 403)
        self.assertEqual(admin.post(path, data={"csrf": csrf, "confirm": "no"}).status_code, 400)
        self.assertEqual(admin.post(path, data={"csrf": csrf, "confirm": "reset"}, follow_redirects=False).status_code, 303)
        for client in (self.client, second):
            profile = client.get('/Jul2026/api/account').json()['account']
            self.assertEqual(profile['opened'], [])
            self.assertEqual(profile['progress_version'], 1)
            self.assertTrue(profile['early_access'])
            self.assertEqual(self.save(client, person['id'], [24]).status_code, 409)
            self.assertEqual(self.click(24, person, client).status_code, 409)
        self.assertEqual(len(self.events()), 1)
        with self.Session() as db:
            self.assertEqual(len(db.scalars(select(CalendarLoginEvent)).all()), 2)
        settings = admin.get('/admin/jul2026/indstillinger')
        self.assertEqual(settings.context['login_counts'][person['id']], 2)
        self.assertEqual(settings.context['door_counts'][person['id']], 1)
        body = {'event_id': event_id, 'account_id': person['id'], 'progress_version': 1}
        self.assertEqual(self.client.post('/Jul2026/api/doors/24/open', headers=HEADERS, json=body).status_code, 409)
        body['event_id'] = str(uuid4())
        self.assertEqual(self.client.post('/Jul2026/api/doors/24/open', headers=HEADERS, json=body).status_code, 200)
        self.assertEqual(second.get('/Jul2026/api/account').json()['account']['opened'], [24])

    def test_login_and_door_metadata_and_failed_login_not_counted(self):
        ua = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Version/18.0 Mobile/15E148 Safari/604.1'
        self.client.headers.update({'User-Agent': ua, 'CF-Connecting-IP': '203.0.113.7'})
        with patch.dict('os.environ', {'RENDER': 'true'}):
            token = self.request_link()
            response = self.client.post('/Jul2026/api/login/consume', headers=HEADERS, json={'token': token})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.client.post('/Jul2026/api/login/consume', headers=HEADERS, json={'token': token}).status_code, 400)
            person = self.client.get('/Jul2026/api/account').json()['account']
            self.click(2, person)
        with self.Session() as db:
            logins = db.scalars(select(CalendarLoginEvent)).all()
            self.assertEqual(len(logins), 1)
            for event in [*logins, *self.events()]:
                self.assertEqual(event.ip_address, '203.0.113.7')
                self.assertIn('iPhone', event.device_type)
                self.assertIn('Safari', event.device_type)
                self.assertEqual(event.user_agent, ua)
        admin, _ = self.admin()
        for kind in ('login', 'doors'):
            history = admin.get('/admin/jul2026/historik', params={'kind': kind, 'email': person['email']})
            self.assertEqual(len(history.context['events']), 1)
            self.assertIn('203.0.113.7', history.text)

    def test_migration_preserves_existing_profile_and_defaults_to_locked(self):
        source = ast.parse(Path("app/main.py").read_text(encoding="utf-8"))
        migrations = next(ast.literal_eval(node.value) for node in source.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "_MIGRATIONS" for target in node.targets))
        upgrade = next(sql for sql in migrations if sql.startswith("ALTER TABLE calendar_visitors"))
        engine = create_engine("sqlite://")
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE calendar_visitors (id INTEGER PRIMARY KEY, email VARCHAR(254) NOT NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)")
            connection.exec_driver_sql("INSERT INTO calendar_visitors (email) VALUES ('existing@example.com')")
            connection.exec_driver_sql(upgrade)
            self.assertEqual(tuple(connection.exec_driver_sql("SELECT email, early_access FROM calendar_visitors").one()), ("existing@example.com", 0))
            connection.exec_driver_sql("CREATE TABLE calendar_door_events (id INTEGER PRIMARY KEY, day INTEGER, result VARCHAR(20))")
            connection.exec_driver_sql("INSERT INTO calendar_door_events (day, result) VALUES (2, 'opened')")
            for sql in migrations:
                if 'progress_version' in sql or sql.startswith('ALTER TABLE calendar_door_events'):
                    connection.exec_driver_sql(sql)
            self.assertEqual(connection.exec_driver_sql('SELECT progress_version FROM calendar_visitors').scalar(), 0)
            self.assertEqual(tuple(connection.exec_driver_sql('SELECT day, result, progress_version, ip_address, device_type, user_agent FROM calendar_door_events').one()), (2, 'opened', 0, None, None, None))
        engine.dispose()
