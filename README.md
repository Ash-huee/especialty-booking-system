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

> **Incremental project:** This repository is currently at **Phase 1 — database + Supabase foundation (in progress, not yet manually verified)**.
> `GET /health` works. Supabase connection (`GET /health/db`) and the SQL
> migration in `database/migrations/001_initial_schema.sql` exist in code
> but are **not complete until manually verified with real credentials**.
> Gemini, Facebook, Excel, Google Calendar, booking logic, and AI agents
> are **not implemented yet**, including no fake/mock versions.

## Current status (Phase 1 — in progress)

CURRENTLY IMPLEMENTED:

* FastAPI application (`app/main.py`)
* Health router (`app/api/routes/health.py`) with `GET /health` (unchanged)
* Database health router (`app/api/routes/db_health.py`) with `GET /health/db`
* Environment-variable configuration (`app/core/config.py`), now including `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`
* Supabase client (`app/integrations/supabase_client.py`, server-side only, never exposes the key)
* PostgreSQL/Supabase migration `database/migrations/001_initial_schema.sql` (customers, conversations, messages, packages, bookings, booking_items, business_settings)
* Unit tests that run **without** real credentials + a separate live-DB integration test (skipped by default)
* Docs: `docs/database.md` (design decisions), updated architecture/log

PLANNED FOR FUTURE PHASES (intentionally deferred):

* Booking engine / availability / confirmation logic, Gemini, conversation manager/chatbot, Facebook Messenger, SMS, website, Excel, Calendar, payments, production auth, AI agents.

## Technology stack

* Python
* FastAPI
* Uvicorn (development server)
* pytest + httpx (testing via FastAPI `TestClient`)
* python-dotenv (optional local `.env` loading)
* supabase (official Supabase Python client — Phase 1 only)

See `requirements.txt`. No Gemini / Messenger / Excel / Calendar libraries yet.

## Current architecture (Phase 1)

```text
Client (browser / test)
  ↓ HTTP
FastAPI app (app/main.py)
  ↓ includes routers
Health router (app/api/routes/health.py) → {"status": "ok"}
DB health router (app/api/routes/db_health.py) → checks Supabase
  ↑                                              ↓
Settings (app/core/config.py) ← env vars   Supabase client
  (APP_NAME/ENV/DEBUG +                        (app/integrations/
   SUPABASE_URL/KEY)                            supabase_client.py)
                                                  ↓
                                            Supabase/PostgreSQL
                                            (source of truth,
                                             see docs/database.md)
```

Future full architecture is documented in `docs/architecture.md`.

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
pytest tests/test_health.py tests/test_config.py tests/test_supabase_client.py tests/test_db_health.py -v
# Live check only (needs migration applied + .env configured):
pytest tests/test_db_integration.py -v
```

## Available endpoint(s)

| Method | Path         | Success response                          | Failure              |
| ------ | ------------ | ----------------------------------------- | -------------------- |
| GET    | `/health`    | `{"status": "ok"}`                        | —                    |
| GET    | `/health/db` | `{"status": "ok", "database": "connected"}` | 503 `not_configured` / `unavailable` (no credentials leaked) |

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
│   │       └── db_health.py
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py
│   ├── models/
│   │   └── __init__.py
│   ├── services/
│   │   └── __init__.py
│   └── integrations/
│       ├── __init__.py
│       └── supabase_client.py
├── database/
│   └── migrations/
│       └── 001_initial_schema.sql
├── tests/
│   ├── __init__.py
│   ├── test_health.py
│   ├── test_config.py
│   ├── test_supabase_client.py
│   ├── test_db_health.py
│   └── test_db_integration.py
├── docs/
│   ├── architecture.md
│   ├── database.md
│   └── development-log.md
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── run.py
```
