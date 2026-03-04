# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Projekt

Sommerhus udlejningssystem til **iebeltoft.dk** (Kløverskrænten 13, 8400 Ebeltoft).
Hostes på **Render** (app + PostgreSQL). Lokalt bruges SQLite.

---

## Udviklingskommandoer

```bash
# Start lokal udviklingsserver (hot-reload)
.venv/Scripts/uvicorn app.main:app --reload

# Installer afhængigheder
.venv/Scripts/pip install -r requirements.txt

# Kør app uden hot-reload (produktion-lignende)
.venv/Scripts/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Ingen build-step — Tailwind CSS køres fra CDN.

---

## Teknologi-stack

| Lag | Teknologi |
|---|---|
| Framework | FastAPI |
| Frontend | Jinja2 templates + HTMX (ingen JS-framework) |
| CSS | Tailwind CSS via CDN |
| Database | SQLite lokalt / PostgreSQL på Render |
| ORM | SQLAlchemy 2.x (sync), `Base.metadata.create_all` ved opstart |
| DB-migration | Startup-ALTER TABLE i `app/main.py` (ikke Alembic, selvom det er i requirements) |
| Auth | Starlette SessionMiddleware + `ADMIN_PASSWORD` env-var |
| Mail | Resend REST API via `httpx` (i `app/services/email.py`) |
| Betaling | Stripe (endnu ikke implementeret) |

---

## Arkitektur

```
app/
├── main.py           # App-opstart: create_all + ALTER TABLE migrations + router-mount
├── database.py       # SQLAlchemy engine + get_db dependency. Retter postgres:// → postgresql://
├── models.py         # ORM-modeller: SeasonInterval, SeasonPrice, Settings, Booking
├── auth.py           # kræv_login() — returnerer redirect hvis ikke logget ind
├── utils.py          # DANSKE_MAANEDER dict (undgår locale-afhængighed)
├── routers/
│   ├── public.py     # Gæste-ruter: /, /booking, /booking/pris (HTMX), /booking/opret, /booking/bekraeftelse/{id}
│   └── admin.py      # Admin-ruter: /admin/* (login, dashboard, sæsoner, priser, bookinger, indstillinger)
├── services/
│   ├── saeson.py     # SAESON_FARVER dict + get_saeson_for_dato() + generer_aarsoverblik()
│   ├── kalender.py   # GAESTE_FARVER + generer_gaeste_kalender() + tjek_overlap() + hent_optagne_datoer()
│   ├── priser.py     # beregn_pris(check_in, check_out, db) → {total, nætter, linjer, fejl}
│   └── email.py      # send_booking_notification(booking, admin_email) via Resend REST API
└── templates/
    ├── base.html             # Public layout (header + main + footer)
    ├── public/
    │   ├── forside.html      # Standalone (extends ikke base.html)
    │   ├── booking.html      # 14-måneders kalender, 2 ad gangen via JS, sticky sidepanel
    │   ├── bekraeftelse.html
    │   └── partials/pris.html  # HTMX partial til prisberegning
    └── admin/
        ├── base_admin.html   # Admin layout med sidebar. aktiv_side-variabel styrer fremhævning
        ├── login.html
        ├── dashboard.html
        ├── saesoner.html
        ├── priser.html
        ├── bookinger.html
        ├── booking_detalje.html
        ├── booking_opret.html
        └── indstillinger.html
```

---

## Database-modeller

**`Settings`** (singleton, id=1) — admin-email, el-pris pr. kWh, vandpris pr. m³

**`SeasonInterval`** — date_from, date_to, season (A–E), label

**`SeasonPrice`** — season (PK), price_per_week, min_nights

**`Booking`** — guest_name/email/phone/address/zip/city/remarks, check_in/out, total_price, status (pending/confirmed/cancelled), stripe_payment_id, notes (admin-noter)

### DB-migrationer
Nye tabeller oprettes automatisk via `create_all()`. Nye kolonner på eksisterende tabeller tilføjes med `ALTER TABLE ... ADD COLUMN` i `app/main.py` (wrapped i try/except — virker for både SQLite og PostgreSQL). **Alembic er installeret men ikke initialiseret.**

---

## Sæsonsystem

Fem sæsoner **A–E** (A=Højsæson, B=Mellemsæson, C=Lavsæson, D=Skuldersæson, E=Vintersæson).
Admin definerer dato-intervaller. Dage uden defineret sæson vises som **optaget** i gæstekalenderen.
Pris = `ugepris ÷ 7 × antal_nætter` per sæson (ophold kan spænde over flere sæsoner).

---

## Nøglemønstre

**HTMX prisberegning:** `booking.html` bruger `hx-trigger="opdaterPris from:body"` → kalder `/booking/pris` → returnerer `partials/pris.html`. JS-siden kalder `htmx.trigger(document.body, 'opdaterPris')` når datoer ændres.

**Kalender-navigation:** Alle 14 måneder renderes i HTML (data til JS-overlap-tjek). JS skjuler/viser 2 ad gangen via `style.display`.

**Admin-auth:** Alle admin-ruter kalder `kræv_login(request)` øverst. Returnerer `RedirectResponse` til `/admin/login` hvis ikke logget ind.

**Settings-singleton:** Hentes med `db.query(models.Settings).filter(id==1).first()` med get-or-create pattern.

---

## Miljøvariabler (.env)

```
DATABASE_URL=sqlite:///./sommerhus.db   # PostgreSQL-URL på Render (sættes automatisk)
ADMIN_PASSWORD=...
SECRET_KEY=...                           # Session-kryptering
RESEND_API_KEY=...                       # Kræver verificeret domæne iebeltoft.dk i Resend
STRIPE_SECRET_KEY=...                    # Endnu ikke implementeret
STRIPE_WEBHOOK_SECRET=...
```

---

## Deploy (Render)

`render.yaml` definerer Blueprint med web-service + PostgreSQL. Push til `master` på GitHub trigger automatisk deploy.
PostgreSQL-URL leveres som `DATABASE_URL` env-var. `app/database.py` retter `postgres://` → `postgresql://` automatisk.

---

## Aktuelt status

**Fase 1 + dele af Fase 2 er implementeret.** Mangler:
- Stripe betaling (Trin 9)
- Bekræftelsesmail til gæst via Resend (Trin 10)
- iCal-eksport
- Minimum nætter-validering på guest-side
