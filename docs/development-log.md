# Development Log

## Phase 0 — Backend foundation

**Date:** 2026-10-03

### Objective

Create a minimal, understandable FastAPI backend foundation that can be
tested before any business logic or external integrations are added.

### What was implemented

* Project structure under `especialty/`:
  `app/`, `app/api/routes/`, `app/core/`, `app/models/`,
  `app/services/`, `app/integrations/`, `tests/`, `docs/`.
* FastAPI application in `app/main.py` with router registration.
* Health router in `app/api/routes/health.py` exposing `GET /health`
  returning `{"status": "ok"}`.
* Environment-variable configuration in `app/core/config.py`
  (`APP_NAME`, `APP_ENV`, `DEBUG` with development defaults).
* `.env.example` with example values (no real `.env` committed).
* `requirements.txt` with only Phase 0 needs:
  `fastapi`, `uvicorn`, `pytest`, `httpx`, `python-dotenv`.
* Basic logging via `logging.basicConfig` (DEBUG/INFO based on `DEBUG`).
* Test `tests/test_health.py` verifying status 200 and body
  `{"status": "ok"}` using FastAPI `TestClient`.
* `run.py` convenience script (`uvicorn app.main:app --reload` equivalent).
* `.gitignore` for Python, venvs, `.env`, IDE, cache, OS files.
* `README.md`, `docs/architecture.md`, this log.

### What was intentionally NOT implemented

* No booking/order/party-package logic.
* No conversation manager or booking engine.
* No database models or migrations.
* No real or fake integrations for Gemini, Facebook/Messenger,
  Microsoft Excel/Graph, Supabase/PostgreSQL, or Google Calendar.
* No authentication, notifications, escalation, or reporting.

### Testing performed (Phase 0 verification — 2026-10-03)

Reported by user — all checks PASS, no code changes made:

* Virtual environment creation/activation: PASS
* Dependencies installed (`pip install -r requirements.txt`): PASS
* FastAPI server starts (`uvicorn app.main:app --reload`): PASS
* `GET /health`: PASS — HTTP status 200 OK
* `GET /openapi.json`: PASS
* `pytest`: PASS

Server log evidence:

```text
INFO: 127.0.0.1:61449 - "GET /health HTTP/1.1" 200 OK
INFO: 127.0.0.1:54328 - "GET /health HTTP/1.1" 200 OK
```

Phase 0 is accepted as tested. No Phase 1 work started.

---

## Phase 1 — Database + Supabase foundation (COMPLETED AND VERIFIED)

**Date:** 2026-10-03
**Verification date:** 2026-10-05

### Objective

Add only the database foundation and Supabase connection. No booking logic,
no AI, no channel integrations.

### What was implemented

* `database/migrations/001_initial_schema.sql`: `customers`, `conversations`,
  `messages`, `packages`, `bookings` (EVENT + FOOD_ORDER), `booking_items`,
  `business_settings` (+1 `Especialty`/2 seed row). UUIDs, FKs, TIMESTAMPTZ,
  TEXT+CHECK instead of ENUMs, NUMERIC money, non-destructive ON DELETE,
  indexes, `updated_at` triggers. See `docs/database.md`.
* `app/core/config.py`: added `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
  (empty = not configured) + `is_supabase_configured()`.
* `app/integrations/supabase_client.py`: `is_configured()`,
  `get_supabase_client()` (None when unconfigured), `check_supabase_connection()`
  (lightweight `business_settings` query, generic errors, never leaks the key).
* `app/api/routes/db_health.py`: `GET /health/db` → 200 `connected`,
  503 `not_configured`/`unavailable`. `GET /health` untouched.
* `requirements.txt`: added `supabase` (official client). `.env.example`:
  placeholders only, no real `.env` created/modified.
* Tests: `test_config.py`, `test_supabase_client.py`, `test_db_health.py`
  (all pass without credentials, mocked); `test_db_integration.py`
  (skipped unless real credentials are set — never fakes success).
* Docs: created `docs/database.md`; updated `README.md`, `docs/architecture.md`.

### What was intentionally NOT implemented

* No repositories/CRUD, booking availability/confirmation, payments.
* No Gemini, conversation manager/chatbot, Messenger/SMS/website.
* No Excel, Calendar, AI agents, production auth.

### Testing performed

* Automated unit suite (no credentials needed): `pytest` (integration test skips automatically).
* Manual verification REQUIRED before Phase 1 is complete (not done yet):
  apply the SQL in Supabase SQL Editor, set `.env`, check
  `GET /health` → 200 `{"status": "ok"}` and
  `GET /health/db` → 200 `{"status": "ok", "database": "connected"}`.

### Final Phase 1 verification (2026-10-05, reported by user)

* Phase 1 database foundation completed.
* Supabase project created.
* Initial database migration (`database/migrations/001_initial_schema.sql`) successfully applied.
* Supabase environment configuration successfully loaded (`.env` with `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` now read via `python-dotenv` in `app/core/config.py`).
* FastAPI `GET /health` passed.
* FastAPI `GET /health/db` returned `connected`.
* Live Supabase integration test (`tests/test_db_integration.py`) passed with real credentials.
* Full pytest suite passed: **14 tests passed**.
* The test suite produced **3 deprecation warnings, but no test failures**.
* The warnings are dependency deprecation warnings (upstream packages signalling a future API change). They are not being addressed yet because they do not affect functionality — all tests pass and both health endpoints behave as specified.

Phase 1 is accepted and ready for Git commit. No Phase 2 work started.

---

## Phase 2 — Deterministic booking engine (COMPLETED AND VERIFIED)

**Date:** 2026-10-05
**Verification date:** 2026-10-06

### Objective

Implement a deterministic booking service (validation, capacity, pricing,
statuses, handoff, Supabase persistence) with no AI and no channel
integrations. The engine — not AI — decides whether a booking is valid.

### What was implemented

* `app/models/booking.py`: `BookingCreateRequest`, `BookingItemInput`
  (structure-only Pydantic), `ValidationError` (`field`/`code`/`message`).
* `app/models/customer.py`: trimming normalization, basic email check,
  shared customer rules.
* `app/services/pricing_service.py`: Decimal-only `calculate_event_price`
  (`guests × price_per_person`) and `calculate_food_order_total`
  (`sum(qty × unit_price)`), quantized to cents.
* `app/services/booking_service.py`: EVENT/FOOD_ORDER requirements,
  service-type whitelist, package active-check, capacity
  (`max_events_per_day` from DB, CANCELLED excluded, food orders exempt),
  customer matching (phone → email → create), PENDING-only creation,
  HUMAN_HANDOFF on unsafe states. No `002` migration — Phase 1 schema
  already stores everything.
* `app/integrations/booking_repository.py`: `SupabaseBookingRepository`
  (`RepositoryError` on failures) — service never touches raw Supabase.
* `app/api/routes/bookings.py`: thin `POST /bookings`
  (201 success / 422 validation / 409 full date / 202 handoff / 503
  unconfigured; unexpected exceptions become handoffs, never internals).
* Tests (mocked via `tests/fakes.py`, no credentials):
  `test_pricing_service`, `test_booking_validation`,
  `test_booking_capacity` (incl. repository query asserting
  `status != CANCELLED`), `test_booking_customer_status`,
  `test_bookings_api`; live `test_booking_integration.py` (skipped
  without credentials, FK-safe cleanup when run).
* Docs: created `docs/booking-engine.md`; updated `README.md`,
  `docs/architecture.md`.

### What was intentionally NOT implemented

* No Gemini, conversation manager/chatbot, Messenger/SMS/website.
* No Excel, Calendar, n8n, AI agents, auth, payments, confirmation flow.

### Testing performed

* New unit tests: 37 passed, plus 10 nullable-field model tests
  (`tests/test_booking_nullable.py`), all mocked (see `tests/fakes.py`).
* Manual verification performed against the real Supabase database —
  see "Final Phase 2 verification" below.

### Final Phase 2 verification (2026-10-06, reported by user, real Supabase)

* Implementation completed: EVENT + FOOD_ORDER bookings, customer matching
  (exact phone → exact email → create), deterministic validation, capacity
  via `business_settings.max_events_per_day`, Decimal pricing, Supabase
  persistence, HUMAN_HANDOFF for unsafe states, PENDING for new bookings.
* Nullable request-model correction discovered during manual testing:
  `event_location` and `special_requests` now accept null at the
  Pydantic layer (`app/models/booking.py`); business validation in
  `booking_service.py` unchanged — EVENT with null `event_location`
  remains invalid, FOOD_ORDER may carry null event fields.
* Automated tests: focused nullable-field tests 10 passed; full pytest
  suite 61 passed, 1 skipped (live-DB test without credentials in that
  shell), 3 pre-existing upstream deprecation warnings, no failures.
* Manual results, all against real Supabase:
  * A. Valid EVENT → 201, persisted, status PENDING.
  * B. Invalid EVENT (missing/null `event_location`) → 422, no booking or
    customer record created.
  * C. Capacity on 2026-10-20: first EVENT → 201, second → 201,
    third → 409 `EVENT_CAPACITY_REACHED`, third booking not created.
  * D. Valid FOOD_ORDER → 201, persisted, `estimated_price` = "600.00"
    (2 × 150 + 3 × 100).
  * E. FOOD_ORDER with no items → 422 `REQUIRED_BOOKING_ITEMS`, nothing created.
  * F. FOOD_ORDER with quantity 0 → 422 `INVALID_ITEM_QUANTITY`, nothing created.
  * G. FOOD_ORDER with negative unit_price → 422 `INVALID_ITEM_PRICE`, nothing created.
  * H. Decimal pricing verified live: 3 × 125.50 + 2 × 249.75 = 876.00
    returned and persisted correctly.
  * I–K. Customer matching verified live: reused by phone, reused by email
    with a different phone, new customer created — no duplicates.
* Major business rules verified: type-specific requirements, service-type
  whitelist, package active-check, capacity counting (CANCELLED excluded,
  food orders exempt), Decimal-only money, PENDING-only creation, handoff
  on unsafe states, validate-before-write ordering.
* Invalid requests were verified not to create database records (B, E, F, G).

Phase 2 is accepted and ready for Git commit. No Phase 3 work started.

### Known limitation (documented, not hidden)

* No multi-table transaction through the Supabase REST client: validate
  everything before writing (customer → booking → items); if item
  insertion fails after the booking row exists, the response is a handoff
  carrying the booking_id for staff reconciliation. A future phase should
  add an atomic Postgres RPC plus orphan tooling.
* Review item (intentional, minimal scope): `customer_email` remains a
  non-nullable string at the request-model layer, so an explicit JSON null
  email fails shape validation instead of reaching business validation.
  Left unchanged during the nullability correction; revisit if a channel
  legitimately sends `customer_email: null`.
