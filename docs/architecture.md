# Especialty Architecture

This document describes the intended long-term architecture and clearly
separates what exists today (Phase 1 in progress) from what is planned
for later phases.

## Long-term conceptual flow

```text
Customer / Channel (Messenger, web, etc.)
  ↓
API / Webhook layer (FastAPI)
  ↓
Conversation Manager (buttons + natural language routing)
  ↓
Gemini AI layer (understand unstructured messages → structured data)
  ↓
Deterministic Booking Engine (validation + business rules)
  ↓
Database / Excel / Calendar / Notifications
  ↓
Reporting
```

The key principle: **AI interprets, deterministic code decides.**
Gemini helps understand what the customer meant; the booking engine
enforces prices, availability, and rules.

## Components

### 1. Channel layer — PLANNED / FUTURE

Entry points where customers talk to the system:

* Facebook Messenger (primary planned channel)
* Possibly web chat / other channels later

Not implemented in Phase 0.

### 2. API layer — CURRENTLY IMPLEMENTED (minimal, Phase 1)

* **Implemented:** FastAPI app (`app/main.py`) with router registration.
* **Implemented:** `GET /health` router (`app/api/routes/health.py`, unchanged).
* **Implemented (Phase 1, needs manual verification):** `GET /health/db`
  router (`app/api/routes/db_health.py`) — 200 `connected` when Supabase
  answers, 503 `not_configured`/`unavailable` otherwise, never leaks credentials.
* **Planned:** webhook endpoints (e.g. Messenger), booking/order endpoints,
  validation with Pydantic models, authentication.

### 3. Conversation Manager — PLANNED / FUTURE

* Routes between structured buttons (predictable actions) and
  natural-language handling.
* Tracks conversation state per customer.
* Decides when to ask clarifying questions vs. proceed.

Not implemented in Phase 0. Placeholder package: `app/services/`.

### 4. Gemini AI layer — PLANNED / FUTURE

* Uses Gemini as the LLM to convert free-text messages into
  structured information (dates, party size, package type, etc.).
* Never writes directly to bookings; output is validated first.

No real or fake Gemini integration exists in Phase 0.
Placeholder package: `app/integrations/`.

### 5. Booking Engine (deterministic) — PLANNED / FUTURE

* Validates structured data against business rules
  (capacity, menu, pricing, time windows).
* Creates/updates bookings, orders, party packages, food trays.
* This is plain Python logic so behavior is predictable and testable.

Not implemented in Phase 0. Placeholder packages:
`app/services/`, `app/models/`.

### 6. Database (Supabase / PostgreSQL) — CURRENTLY IMPLEMENTED (foundation, Phase 1 in progress)

* **Implemented:** migration `database/migrations/001_initial_schema.sql`
  creating `customers`, `conversations`, `messages`, `packages`,
  `bookings`, `booking_items`, `business_settings` (see `docs/database.md`).
* **Implemented:** server-side Supabase client (`app/integrations/supabase_client.py`)
  + config (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`).
* **Not yet verified:** migration has not been applied in Supabase and
  `GET /health/db` has not been manually tested with real credentials,
  so Phase 1 is not marked complete.
* Application source of truth for customers, bookings, orders, messages.
* Supabase/PostgreSQL is the intended backend.

No repositories / CRUD services yet — those come with Phase 2 booking logic.

### 7. Microsoft Excel integration — PLANNED / FUTURE

* Staff-facing booking records in Excel (via Microsoft Graph or export).
* The database remains the source of truth; Excel is a view/reporting aid.

No real or fake Excel integration exists in Phase 0.

### 8. Google Calendar integration — PLANNED / FUTURE

* Creates/updates calendar events for confirmed bookings.
* Handles scheduling conflicts and reminders.

No real or fake Calendar integration exists in Phase 0.

### 9. Human escalation — PLANNED / FUTURE

* When AI confidence is low or a rule cannot be satisfied safely,
  the conversation is handed to a human staff member.
* Requires conversation state + staff notification channel.

Not implemented in Phase 0.

### 10. Reporting — PLANNED / FUTURE

* Automated reports (bookings per day, revenue, popular packages, etc.).
* Built on top of database records.

Not implemented in Phase 0.

## Summary: implemented vs. future

| Area | Phase 1 status |
| ---- | -------------- |
| FastAPI app + health endpoint | CURRENTLY IMPLEMENTED |
| Env-based config + basic logging | CURRENTLY IMPLEMENTED (now incl. Supabase vars) |
| Health test (pytest) | CURRENTLY IMPLEMENTED |
| Supabase client + `GET /health/db` + migration SQL | CURRENTLY IMPLEMENTED (needs manual verification) |
| Conversation manager | PLANNED / FUTURE |
| Gemini AI layer | PLANNED / FUTURE |
| Booking engine + models | PLANNED / FUTURE |
| Supabase repositories / CRUD | PLANNED / FUTURE (Phase 2) |
| Excel integration | PLANNED / FUTURE |
| Google Calendar integration | PLANNED / FUTURE |
| Facebook Messenger | PLANNED / FUTURE |
| Human escalation | PLANNED / FUTURE |
| Reporting / notifications | PLANNED / FUTURE |
