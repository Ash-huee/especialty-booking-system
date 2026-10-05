# Especialty

Especialty is a food-service / catering business automation system.

The long-term goal is to support:

* Catering / event bookings
* Food orders
* Party packages
* Food trays
* Customer conversations (buttons + natural language)
* AI-assisted understanding of customer messages
* Facebook Messenger channel
* Microsoft Excel staff booking records
* Google Calendar scheduling
* Supabase / PostgreSQL as the source of truth
* Human escalation when AI is uncertain
* Automated reporting

> **Incremental project:** This repository is currently at **Phase 2 — deterministic booking engine (complete and manually verified)**.
> `GET /health`, `GET /health/db`, and `POST /bookings` (validation, capacity,
> Decimal pricing, customer matching, PENDING/HANDOFF handling) are implemented
> and verified against the real Supabase database.
> Gemini, Facebook, Excel, Google Calendar, chatbot logic, and AI agents
> are **not implemented yet**, including no fake/mock versions.

## Current status (Phase 2 — complete and verified)

CURRENTLY IMPLEMENTED:

* FastAPI application (`app/main.py`)
* Health routers: `GET /health` (unchanged), `GET /health/db` (Supabase probe)
* Deterministic booking engine (no AI):
  * Request models (`app/models/booking.py`, `app/models/customer.py`)
  * Business logic (`app/services/booking_service.py`) — validation, capacity, customer matching, statuses, handoff
  * Decimal-safe pricing (`app/services/pricing_service.py`)
  * Supabase data access (`app/integrations/booking_repository.py`)
  * Thin route `POST /bookings` (`app/api/routes/bookings.py`, no rules in the route)
* Environment-variable configuration incl. Supabase vars + `.env` loading
* Migration `database/migrations/001_initial_schema.sql` (unchanged, no Phase 2 migration needed)
* Unit tests without credentials + separate live-DB tests (skipped by default)
* Docs: `docs/database.md`, `docs/booking-engine.md` (design decisions)

PLANNED FOR FUTURE PHASES (intentionally deferred):

* Gemini extraction, conversation manager/chatbot, Facebook Messenger, SMS, website, Excel, Calendar, n8n, AI agents, payments, production auth, confirmation flow.

## Technology stack

* Python
* FastAPI
* Uvicorn (development server)
* pytest + httpx (testing via FastAPI `TestClient`)
* python-dotenv (optional local `.env` loading)
* supabase (official Supabase Python client — Phase 1 only)

No new dependencies in Phase 2 (Pydantic arrives with FastAPI;
money uses stdlib `decimal`). No Gemini / Messenger / Excel / Calendar libraries yet.

## Current architecture (Phase 2)

```text
POST /bookings (thin route, app/api/routes/bookings.py)
  ↓ BookingCreateRequest (app/models/)
BookingService (app/services/booking_service.py: validation,
  capacity from business_settings, Decimal pricing, PENDING/HANDOFF)
  ↓ via repository
SupabaseBookingRepository (app/integrations/booking_repository.py)
  ↓
Supabase/PostgreSQL (source of truth, see docs/database.md)

GET /health → {"status": "ok"}            (unchanged)
GET /health/db → Supabase probe           (Phase 1)
```

AI (future) will only produce the request object — it never decides.
Full architecture: `docs/architecture.md`. Engine detail: `docs/booking-engine.md`.

## Installation

1. Create and activate a virtual environment (see below).
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## How to create and activate a virtual environment

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Deactivate at any time with:

```bash
deactivate
```

## How to run the application

From the `especialty/` directory (where `run.py` lives):

```bash
uvicorn app.main:app --reload
```

or:

```bash
python run.py
```

Then open:

* Health check: <http://127.0.0.1:8000/health>
* Interactive API docs: <http://127.0.0.1:8000/docs>

### Configuration

Copy the example file for local development:

Windows:

```powershell
copy .env.example .env
```

macOS / Linux:

```bash
cp .env.example .env
```

Supported variables (see `app/core/config.py`):

| Variable                  | Default       | Description                                  |
| ------------------------- | ------------- | -------------------------------------------- |
| `APP_NAME`                | `Especialty`  | Application display name                     |
| `APP_ENV`                 | `development` | Environment name                             |
| `DEBUG`                   | `True`        | `True`/`False` log level                     |
| `SUPABASE_URL`            | _(empty)_     | Supabase project URL (Phase 1, server-side)  |
| `SUPABASE_SERVICE_ROLE_KEY` | _(empty)_   | Supabase service-role key — **never commit, never expose** |

Empty Supabase values mean “not configured”: unit tests pass and
`GET /health/db` returns 503 `not_configured`.

## How to run tests

From the `especialty/` directory:

```bash
pytest
```

Normal unit tests run **without** Supabase credentials.
The live-DB test (`tests/test_db_integration.py`) is skipped automatically
unless `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are set:

```bash
pytest tests/test_health.py tests/test_config.py tests/test_supabase_client.py tests/test_db_health.py tests/test_pricing_service.py tests/test_booking_validation.py tests/test_booking_capacity.py tests/test_booking_customer_status.py tests/test_bookings_api.py -v
# Live checks only (need migration applied + .env configured):
pytest tests/test_db_integration.py tests/test_booking_integration.py -v
```

## Available endpoint(s)

| Method | Path         | Success response                          | Failure              |
| ------ | ------------ | ----------------------------------------- | -------------------- |
| GET    | `/health`    | `{"status": "ok"}`                        | —                    |
| GET    | `/health/db` | `{"status": "ok", "database": "connected"}` | 503 `not_configured` / `unavailable` (no credentials leaked) |
| POST   | `/bookings`  | 201 `{"status":"success","booking_id":...,"booking_status":"PENDING","estimated_price":...}` | 422 `validation_error` (structured `{field,code,message}`), 409 full date (`EVENT_CAPACITY_REACHED`), 202 `human_handoff`, 503 unconfigured DB |

## Database setup (manual, Phase 1)

1. Apply `database/migrations/001_initial_schema.sql` once in the Supabase SQL Editor (see `docs/database.md`).
2. Verify `SELECT * FROM business_settings;` returns `Especialty, 2`.
3. Set `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` in local `.env` (never commit).
4. `GET /health/db` should return 200 `connected`.

## Project structure

```text
especialty/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── health.py
│   │       ├── db_health.py
│   │       └── bookings.py
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── booking.py
│   │   └── customer.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── booking_service.py
│   │   └── pricing_service.py
│   └── integrations/
│       ├── __init__.py
│       ├── supabase_client.py
│       └── booking_repository.py
├── database/
│   └── migrations/
│       └── 001_initial_schema.sql
├── tests/
│   ├── __init__.py
│   ├── test_health.py
│   ├── test_config.py
│   ├── test_supabase_client.py
│   ├── test_db_health.py
│   ├── test_db_integration.py
│   ├── fakes.py
│   ├── test_pricing_service.py
│   ├── test_booking_validation.py
│   ├── test_booking_capacity.py
│   ├── test_booking_customer_status.py
│   ├── test_bookings_api.py
│   └── test_booking_integration.py
├── docs/
│   ├── architecture.md
│   ├── database.md
│   ├── booking-engine.md
│   └── development-log.md
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── run.py
```
