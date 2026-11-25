import unittest
import ast
from pathlib import Path
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import patch
from sqlalchemy import select, create_engine
from app.models import CalendarSnakeProfile as Profile, CalendarSnakeRound as Round, CalendarVisitor, CalendarSnakeEvent
from app.routers import christmas_snake as routes
from app.services.christmas_snake import Game, replay, MAX_TICKS
import test_christmas_accounts as account_tests

HEADERS = account_tests.HEADERS
ROOT = '/Jul2026/api/snake'


class SnakeRulesTests(unittest.TestCase):
    def test_respawn_preserves_length_points_and_has_a_free_next_cell(self):
        for length in range(3,400):
            game=Game(1,3)
            game.body=[(x,y) for y in range(20) for x in range(20)][:length]
            game.score=(length-3)*10
            game.lives=1;game.bonus_life=True;game.life_lost=True
            game.food=(10,10)
            game.respawn()
            self.assertEqual(len(game.body),length)
            self.assertEqual(len(set(game.body)),length)
            self.assertEqual(game.score,(length-3)*10)
            self.assertEqual((game.lives,game.bonus_life),(1,True))
            self.assertNotIn((11,10),game.body)
            self.assertNotIn(game.food,game.body)
            for a,b in zip(game.body,game.body[1:]):
                self.assertEqual(abs(a[0]-b[0])+abs(a[1]-b[1]),1)
            game.step()
            self.assertFalse(game.life_lost)
            self.assertEqual(game.lives,1)

    def test_new_length_preserving_round_replays_identically(self):
        game=Game(1,3)
        for tick in range(1,14):game.step(3 if tick==3 else None)
        self.assertEqual((len(game.body),game.score,game.lives),(4,10,1))
        game.respawn()
        self.assertEqual(game.body,[(10,10),(9,10),(8,10),(7,10)])
        for _ in range(10):game.step()
        verified=replay(1,23,[SimpleNamespace(tick=3,direction=3)],3)
        self.assertEqual((len(verified.body),verified.score,verified.lives),(len(game.body),10,0))

    def test_round_migration_preserves_legacy_rules(self):
        source=ast.parse(Path('app/main.py').read_text(encoding='utf-8'))
        migrations=next(ast.literal_eval(n.value) for n in source.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_MIGRATIONS' for t in n.targets))
        sql=next(s for s in migrations if s.startswith('ALTER TABLE calendar_snake_rounds'))
        engine=create_engine('sqlite://')
        with engine.begin() as db:
            db.exec_driver_sql('CREATE TABLE calendar_snake_rounds (id VARCHAR(36) PRIMARY KEY, seed INTEGER)')
            db.exec_driver_sql("INSERT INTO calendar_snake_rounds (id,seed) VALUES ('old-round',42)")
            db.exec_driver_sql(sql)
            self.assertEqual(tuple(db.exec_driver_sql('SELECT id,seed,rules_version FROM calendar_snake_rounds').one()),('old-round',42,1))
        engine.dispose()
    def test_two_lives_preserve_score_and_replay(self):
        game=Game(1,2)
        for tick in range(1,14):
            game.step(3 if tick==3 else None)
        self.assertEqual((game.score,game.lives,game.life_lost,game.over),(10,1,True,False))
        with self.assertRaises(ValueError):
            replay(1,13,[SimpleNamespace(tick=3,direction=3)],2)
        game.respawn()
        self.assertEqual(game.body,[(10,10),(9,10),(8,10)])
        for _ in range(10):game.step()
        self.assertTrue(game.over)
        self.assertEqual((game.lives,game.score),(0,10))
        verified=replay(1,23,[SimpleNamespace(tick=3,direction=3)],2)
        self.assertEqual((verified.lives,verified.score),(0,10))

    def test_bonus_life_only_once_and_strictly_above_500(self):
        game=Game(1,2)
        game.score=490;game.food=(11,10);game.step()
        self.assertEqual((game.score,game.lives,game.bonus_life),(500,2,False))
        game.food=(12,10);game.step()
        self.assertEqual((game.score,game.lives,game.bonus_life),(510,3,True))
        game.food=(13,10);game.step()
        self.assertEqual(game.lives,3)
        game.lives=2;game.food=(14,10);game.step()
        self.assertEqual(game.lives,2)

    def test_seed_growth_collision_and_replay(self):
        game = replay(1, 13, [SimpleNamespace(tick=3, direction=3)])
        self.assertEqual(game.score, 10)
        self.assertEqual(game.body[0], (12, 0))
        self.assertTrue(game.over)
        self.assertEqual(game.elapsed_ms, 2080)
        with self.assertRaises(ValueError):
            replay(1, 12, [SimpleNamespace(tick=3, direction=3)])
        with self.assertRaises(ValueError):
            replay(1, 14, [SimpleNamespace(tick=3, direction=3)])
        for turns in ([SimpleNamespace(tick=1, direction=2)], [SimpleNamespace(tick=3, direction=3), SimpleNamespace(tick=2, direction=0)]):
            with self.assertRaises(ValueError):
                replay(1, 13, turns)

    def test_tail_is_free_when_moving_and_body_is_not(self):
        game=Game(1)
        game.body=[(2,2),(2,3),(1,3),(1,2)]
        game.direction=2
        game.food=(9,9)
        game.step()
        self.assertFalse(game.over)
        self.assertEqual(game.body[0], (1,2))
        game.body=[(2,2),(3,2),(3,3),(2,3),(1,3)]
        game.direction=0
        game.step(1)
        self.assertTrue(game.over)

    def test_speed_limit_and_full_board_win(self):
        game=Game(1)
        game.score=50
        self.assertEqual(game.interval,150)
        game.score=500
        self.assertEqual(game.interval,80)
        game.body=[(0,0)]+[(x,y) for y in range(20) for x in range(20) if (x,y) not in ((0,0),(1,0))]
        game.score=3960
        game.food=(1,0)
        game.step()
        self.assertTrue(game.won and game.over)
        self.assertIsNone(game.food)
        self.assertEqual(game.score,3970)


class SnakeApiTests(unittest.TestCase):
    def test_player_name_survives_another_device_and_score_save(self):
        person=self.login()
        self.assertEqual(self.preferences(person,'Juleven',False).status_code,200)
        round=self.start(person);self.now+=timedelta(seconds=3)
        self.finish(person,round)
        second=self.device();self.now+=timedelta(minutes=2);self.login(client=second)
        profile=second.get(ROOT+'/profile').json()['profile']
        self.assertEqual((profile['display_name'],profile['best_score'],profile['is_public']),('Juleven',10,True))
        self.assertEqual(self.preferences(person,'Juleven',True,second).status_code,200)
        self.assertEqual(self.client.get(ROOT+'/leaderboard').json()['players'][0]['name'],'Juleven')

    device=account_tests.CalendarAccountTests.device
    request_link=account_tests.CalendarAccountTests.request_link
    login=account_tests.CalendarAccountTests.login
    tearDown=account_tests.CalendarAccountTests.tearDown

    def setUp(self):
        account_tests.CalendarAccountTests.setUp(self)
        self.app.include_router(routes.router)
        patch.object(routes.secrets,'randbelow',return_value=0).start()

    def start(self, person, client=None):
        response=(client or self.client).post(ROOT+'/rounds',headers=HEADERS,json={'account_id':person['id']})
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def finish(self, person, round, ticks=13, turns=None, client=None):
        return (client or self.client).post(ROOT+f"/rounds/{round['round_id']}/finish",headers=HEADERS,json={'account_id':person['id'],'ticks':ticks,'turns':[{'tick':3,'direction':3}] if turns is None else turns})

    def preferences(self, person, name, public=True, client=None):
        return (client or self.client).post(ROOT+'/profile',headers=HEADERS,json={'account_id':person['id'],'display_name':name,'is_public':public})

    def test_unnamed_record_is_atomic_and_shared_across_devices(self):
        person=self.login()
        round=self.start(person)
        self.now+=timedelta(seconds=3)
        saved=self.finish(person,round)
        self.assertEqual(saved.status_code,200,saved.text)
        self.assertEqual(saved.json()['score'],10)
        self.assertTrue(saved.json()['profile']['is_public'])
        self.assertEqual(self.client.get(ROOT+'/leaderboard').json()['players'],[])
        self.assertEqual(self.finish(person,round).status_code,200)
        self.assertEqual(self.finish(person,round,ticks=10,turns=[]).status_code,409)
        lower=self.start(person)
        self.now+=timedelta(seconds=3)
        self.assertEqual(self.finish(person,lower,ticks=10,turns=[]).json()['profile']['best_score'],10)
        self.now+=timedelta(minutes=2)
        other=self.device()
        self.login(client=other)
        self.assertEqual(other.get(ROOT+'/profile').json()['profile']['best_score'],10)
        with self.Session() as db:
            self.assertEqual(len(db.scalars(select(Round).where(Round.finished_at.is_not(None))).all()),2)

    def test_named_scores_always_appear_and_never_expose_email(self):
        person=self.login()
        for name in ('a','...','a@example.com','https://bad','😀😀','--','a'*21):
            self.assertEqual(self.preferences(person,name).status_code,422)
        self.assertEqual(self.preferences(person,' Jule  Nisse ').json()['profile']['display_name'],'Jule Nisse')
        other=self.device()
        second=self.login('second@example.com',other)
        self.assertEqual(self.preferences(second,'jule nisse',client=other).status_code,409)
        round=self.start(person)
        self.now+=timedelta(seconds=3)
        self.finish(person,round)
        board=self.client.get(ROOT+'/leaderboard')
        self.assertEqual(board.json()['players'],[{'rank':1,'name':'Jule Nisse','score':10}])
        self.assertNotIn(person['email'],board.text)
        self.preferences(person,'Nyt Navn')
        self.assertEqual(self.client.get(ROOT+'/leaderboard').json()['players'][0]['name'],'Nyt Navn')
        self.preferences(person,'Nyt Navn',False)
        self.assertTrue(self.client.get(ROOT+'/profile').json()['profile']['is_public'])
        self.assertEqual(self.client.get(ROOT+'/leaderboard').json()['players'][0]['name'],'Nyt Navn')
        with self.Session() as db:
            db.get(Profile,(person['id'],2026)).is_public=False
            db.commit()
        self.assertEqual(self.client.get(ROOT+'/leaderboard').json()['players'][0]['name'],'Nyt Navn')
        self.assertEqual(self.client.get(ROOT+'/profile').json()['profile']['best_score'],10)

    def test_invalid_replays_time_ownership_and_origin(self):
        self.assertIsNone(self.client.get(ROOT+'/profile').json()['profile'])
        self.assertEqual(self.client.post(ROOT+'/rounds',headers=HEADERS,json={'account_id':1}).status_code,401)
        person=self.login()
        self.assertEqual(self.client.post(ROOT+'/rounds',json={'account_id':person['id']}).status_code,403)
        self.assertEqual(self.client.post(ROOT+'/rounds',headers=HEADERS,json={'account_id':person['id']+1}).status_code,409)
        round=self.start(person)
        self.assertEqual(self.finish(person,round).status_code,422) # Played too quickly.
        self.now+=timedelta(seconds=3)
        for ticks,turns in ((12,[{'tick':3,'direction':3}]),(14,[{'tick':3,'direction':3}]),(13,[{'tick':1,'direction':2}]),(13,[{'tick':3,'direction':3},{'tick':3,'direction':0}]),(MAX_TICKS+1,[])):
            self.assertEqual(self.finish(person,round,ticks,turns).status_code,422)
        other=self.device()
        second=self.login('second@example.com',other)
        self.assertEqual(self.finish(second,round,client=other).status_code,404)
        self.assertEqual(self.finish(second,round).status_code,409)
        self.assertEqual(self.finish(person,{'round_id':str(uuid4())}).status_code,404)
        self.now+=timedelta(hours=3)
        self.assertEqual(self.finish(person,round).status_code,422)
        self.assertEqual(self.client.get(ROOT+'/profile').json()['profile']['best_score'],0)

    def test_top_ten_ties_and_start_limit(self):
        person=self.login()
        with self.Session() as db:
            for i in range(12):
                visitor=CalendarVisitor(email=f'player{i}@example.com')
                db.add(visitor);db.flush()
                db.add(Profile(visitor_id=visitor.id,year=2026,display_name=f'Nisse {i}',name_key=f'nisse {i}',is_public=True,best_score=100,achieved_at=self.now+timedelta(seconds=i)))
            db.commit()
        board=self.client.get(ROOT+'/leaderboard').json()['players']
        self.assertEqual(len(board),10)
        self.assertEqual([p['name'] for p in board],[f'Nisse {i}' for i in range(10)])
        for _ in range(20):
            self.start(person)
        self.assertEqual(self.client.post(ROOT+'/rounds',headers=HEADERS,json={'account_id':person['id']}).status_code,429)

    def test_versioned_round_preserves_old_games_and_validates_new_lives(self):
        person=self.login()
        response=self.client.post(ROOT+'/rounds',headers=HEADERS,json={'account_id':person['id'],'rules_version':2})
        self.assertEqual(response.status_code,200)
        round=response.json();self.assertEqual(round['rules_version'],2)
        self.now+=timedelta(seconds=4)
        self.assertEqual(self.finish(person,round).status_code,422)
        self.assertEqual(self.finish(person,round,ticks=23).status_code,200)
        old=self.start(person)
        self.assertEqual(old['rules_version'],1)
        self.now+=timedelta(seconds=3)
        self.assertEqual(self.finish(person,old).status_code,200)
        response=self.client.post(ROOT+'/rounds',headers=HEADERS,json={'account_id':person['id'],'rules_version':3})
        self.assertEqual(response.status_code,200)
        new=response.json();self.assertEqual(new['rules_version'],3)
        self.now+=timedelta(seconds=4)
        self.assertEqual(self.finish(person,new,ticks=23).status_code,200)

    def test_click_logs_server_metadata_guest_and_idempotency(self):
        body={'event_id':str(uuid4()),'action':'open'}
        self.client.headers['User-Agent']='iPhone Mobile Safari/604.1'
        self.assertEqual(self.client.post(ROOT+'/events',headers=HEADERS,json=body).status_code,200)
        self.assertEqual(self.client.post(ROOT+'/events',headers=HEADERS,json=body).status_code,200)
        person=self.login()
        self.assertEqual(self.client.post(ROOT+'/events',headers=HEADERS,json=body).status_code,409)
        body={'event_id':str(uuid4()),'action':'replay'}
        self.assertEqual(self.client.post(ROOT+'/events',headers=HEADERS,json=body).status_code,200)
        self.assertEqual(self.client.post(ROOT+'/events',json=body).status_code,403)
        self.assertEqual(self.client.post(ROOT+'/events',headers=HEADERS,json={'event_id':str(uuid4()),'action':'wrong'}).status_code,422)
        with self.Session() as db:
            events=db.scalars(select(CalendarSnakeEvent).order_by(CalendarSnakeEvent.clicked_at,CalendarSnakeEvent.action)).all()
            self.assertEqual(len(events),2)
            self.assertIsNone(events[0].visitor_id)
            self.assertEqual(events[1].visitor_id,person['id'])
            self.assertIn('iPhone',events[0].device_type)
            self.assertEqual(events[0].clicked_at,self.now)
