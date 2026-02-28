# Sommerhus Udlejningssystem — iebeltoft.dk

## Projekt-overblik
Python-baseret udlejningssystem til sommerhus. Hostes på Railway.
Domæne: **iebeltoft.dk**

---

## Teknologi-stack

| Lag | Teknologi | Bemærkning |
|---|---|---|
| Framework | FastAPI | Moderne Python API-framework |
| Frontend | Jinja2 templates + HTMX | Interaktivt UI uden Node.js/React |
| Database | PostgreSQL | Hostes på Railway |
| ORM | SQLAlchemy + Alembic | ORM + databasemigrationer |
| Betaling | Stripe | Kort + MobilePay Checkout |
| Mail | Resend.com | Automatiske bekræftelsesmails |
| Hosting | Railway | App + PostgreSQL i én platform |
| CSS | Tailwind CSS (CDN) | Ingen build-step |
| Sprog | Dansk | Al tekst på dansk |

---

## Features — prioriteret

### Fase 1: Fundament
1. Projektstruktur + FastAPI + PostgreSQL (lokalt)
2. Database-modeller (Booking, Sæson, Pris)
3. Admin-login (simpel adgangskode, session-baseret)
4. Sæsonkalender i admin (definer A/B/C/D/E-sæson per dato-interval)
5. Sæsonpriser i admin (pris per nat for hver sæson)
6. Kalender-visning til gæster (ledige/optagne datoer med sæsonfarve)
7. Booking-formular (gæst: navn, email, telefon, datoer)
8. Admin-panel: liste og håndtering af bookinger

### Fase 2: Betaling & notifikationer
9. Stripe betaling (kort + MobilePay) ved booking
10. Automatisk bekræftelsesmail til gæst (Resend)
11. Notifikationsmail til admin ved ny booking

### Fase 3: Deploy & polish
12. Deploy til Railway
13. Domæne: iebeltoft.dk tilknyttet
14. Minimum antal nætter (kan sættes per sæson)
15. iCal-eksport (Apple Kalender / Google Kalender)
16. Ryddedag/skiftedag-regler

---

## Sæsonsystem

Fem sæsoner: **A, B, C, D, E** — admin definerer hvilke datoer der tilhører hvilken sæson.

| Sæson | Eksempel | Typisk periode |
|---|---|---|
| A | Højsæson | Juli–august |
| B | Mellemsæson | Juni, tidlig aug |
| C | Lavsæson | Maj, september |
| D | Skuldersæson | April, oktober |
| E | Vintersæson | November–marts |

Priser er **per uge** per sæson. Delpris ved kortere ophold beregnes som ugepris/7 × antal nætter.

Admin-panel: Man kan oprette sæsonintervaller (fx "1. juli – 31. august = Sæson A") og sætte ugepris per sæson.

---

## Admin-panel features

- Login med adgangskode (simpel, session-baseret — ingen brugerdb fra start)
- Kalender-overblik over alle bookinger
- Opret/rediger/slet bookinger manuelt
- Definer sæsonintervaller (dato-fra, dato-til, sæson A–E)
- Sæt priser per sæson
- Se gæsteinformation
- Markér booking som betalt/ikke-betalt
- Send bekræftelsesmail manuelt

---

## Database-modeller (overordnet)

```
Booking
  - id, created_at
  - guest_name, guest_email, guest_phone
  - check_in (date), check_out (date)
  - total_price (decimal)
  - status (pending / confirmed / cancelled)
  - stripe_payment_id
  - notes (admin-noter)

SeasonInterval
  - id
  - date_from, date_to
  - season (A/B/C/D/E)
  - label (valgfri tekst, fx "Sommer 2025")

SeasonPrice
  - season (A/B/C/D/E)  ← unik nøgle
  - price_per_week (decimal)
  - min_nights (heltal)
```

---

## Step-by-step byggeplan

```
Trin 1:  Projektstruktur + FastAPI hello world + PostgreSQL tilsluttet
Trin 2:  Database-modeller + Alembic migrationer
Trin 3:  Admin-login (adgangskode + session)
Trin 4:  Admin: sæsonintervaller (CRUD)
Trin 5:  Admin: sæsonpriser (CRUD)
Trin 6:  Gæste-kalender (vis ledige datoer, sæsonfarver)
Trin 7:  Booking-formular + prisberegning
Trin 8:  Admin: booking-oversigt (se/rediger/slet)
Trin 9:  Stripe betaling (checkout session)
Trin 10: Bekræftelsesmail til gæst (Resend)
Trin 11: Notifikationsmail til admin
Trin 12: Deploy til Railway + iebeltoft.dk domæne
Trin 13: Minimum nætter per sæson
Trin 14: iCal-eksport
```

---

## Projektstruktur (mål)

```
sommerhus/
├── app/
│   ├── main.py              # FastAPI app
│   ├── database.py          # DB-forbindelse
│   ├── models.py            # SQLAlchemy modeller
│   ├── schemas.py           # Pydantic schemas
│   ├── routers/
│   │   ├── public.py        # Gæste-sider (kalender, booking)
│   │   ├── admin.py         # Admin-panel
│   │   └── payments.py      # Stripe webhooks
│   ├── services/
│   │   ├── booking.py       # Booking-logik
│   │   ├── pricing.py       # Prisberegning per sæson
│   │   └── email.py         # Resend mail-afsendelse
│   └── templates/
│       ├── base.html
│       ├── public/
│       │   ├── calendar.html
│       │   └── booking.html
│       └── admin/
│           ├── login.html
│           ├── dashboard.html
│           ├── bookings.html
│           └── seasons.html
├── static/
│   └── css/, js/
├── alembic/                 # DB-migrationer
├── .env                     # Secrets (ikke i git)
├── requirements.txt
├── Procfile                 # Railway start-kommando
└── CLAUDE.md
```

---

## Miljøvariabler (.env)

```
DATABASE_URL=postgresql://...
ADMIN_PASSWORD=...
SECRET_KEY=...           # Session-kryptering
STRIPE_SECRET_KEY=...
STRIPE_WEBHOOK_SECRET=...
RESEND_API_KEY=...
ADMIN_EMAIL=...          # Modtager af admin-notifikationer
```

---

## Næste skridt
**Aktuelt trin: Trin 1** — Projektstruktur + FastAPI + PostgreSQL
