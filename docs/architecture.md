# Especialty Architecture

This document describes the intended long-term architecture and clearly
separates what exists today (Phase 3 complete and verified) from what is
planned for later phases.

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

### 2. API layer — CURRENTLY IMPLEMENTED (Phase 2)

* **Implemented:** FastAPI app (`app/main.py`) with router registration.
* **Implemented:** `GET /health` router (`app/api/routes/health.py`, unchanged).
* **Implemented:** `GET /health/db` router (`app/api/routes/db_health.py`).
* **Implemented (Phase 2, verified):** `POST /bookings`
  (`app/api/routes/bookings.py`) — thin route delegating to the booking
  service (201 success / 422 validation / 409 full date / 202 handoff / 503 unconfigured).
* **Implemented (Phase 3, verified):**
  `POST /conversations/messages` + `GET /conversations/{id}`
  (`app/api/routes/conversations.py`) — thin local-test routes over the
  conversation manager (201 / 422 / 404 / 503, no AI, no channels).
* **Planned:** channel webhook endpoints (e.g. Messenger), authentication.

### 3. Conversation Manager — CURRENTLY IMPLEMENTED (Phase 3, basic flow)

* **Implemented:** `app/services/conversation_manager.py` — local-test flow
  (find/create customer → reuse/open active conversation → store customer
  message). No intent inference, no bookings, no AI (see
  `docs/conversation-layer.md`).
* **Implemented:** conversation state (`conversation_service.py`: open,
  retrieve, deterministic status transitions) and message history
  (`message_service.py`: append + oldest-first reads) on the Phase 1
  `conversations`/`messages` tables. No migration was needed.
* **Planned (future):** routing between structured buttons and
  natural-language handling, clarifying questions, Gemini interpretation.

### 4. Gemini AI layer — PLANNED / FUTURE

* Uses Gemini as the LLM to convert free-text messages into
  structured information (dates, party size, package type, etc.).
* Never writes directly to bookings; output is validated first.

No real or fake Gemini integration exists in Phase 0.
Placeholder package: `app/integrations/`.

### 5. Booking Engine (deterministic) — CURRENTLY IMPLEMENTED (Phase 2 verified)

* **Implemented:** `app/services/booking_service.py` — EVENT/FOOD_ORDER
  validation, capacity (limit from `business_settings`), Decimal pricing,
  customer matching (phone → email → create), PENDING-only creation,
  `HUMAN_HANDOFF` on unsafe states. No AI involved (see `docs/booking-engine.md`).
* **Implemented:** request models (`app/models/booking.py`,
  `app/models/customer.py`) and pricing (`app/services/pricing_service.py`).
* **Implemented:** data access (`app/integrations/booking_repository.py`)
  keeping Supabase details out of the service.
* **Verified:** `POST /bookings` manually tested against real Supabase
  (valid EVENT/FOOD_ORDER persist as PENDING; invalid requests persist
  nothing; capacity enforced) — see `docs/development-log.md`. Phase 2 complete.
* Validates structured data against business rules
  (capacity, menu, pricing, time windows).
* Creates/updates bookings, orders, party packages, food trays.
* This is plain Python logic so behavior is predictable and testable.

### 6. Database (Supabase / PostgreSQL) — CURRENTLY IMPLEMENTED (foundation verified Phase 1)

* **Implemented:** migration `database/migrations/001_initial_schema.sql`
  creating `customers`, `conversations`, `messages`, `packages`,
  `bookings`, `booking_items`, `business_settings` (see `docs/database.md`).
* **Implemented:** server-side Supabase client (`app/integrations/supabase_client.py`)
  + config (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`).
* **Implemented (Phase 2):** booking data-access layer
  (`app/integrations/booking_repository.py`). No schema change was needed.
* Application source of truth for customers, bookings, orders, messages.
* Supabase/PostgreSQL is the intended backend.

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

Not implemented — future phase.

### 10. Reporting — PLANNED / FUTURE

* Automated reports (bookings per day, revenue, popular packages, etc.).
* Built on top of database records.

Not implemented — future phase.

## Summary: implemented vs. future

| Area | Phase 2 status |
| ---- | -------------- |
| FastAPI app + health endpoints | CURRENTLY IMPLEMENTED |
| Env-based config + basic logging | CURRENTLY IMPLEMENTED (incl. Supabase vars + `.env` loading) |
| Health tests (pytest) | CURRENTLY IMPLEMENTED |
| Supabase client + `GET /health/db` + migration SQL | CURRENTLY IMPLEMENTED (verified Phase 1) |
| Booking engine + models + pricing | CURRENTLY IMPLEMENTED (verified Phase 2) |
| `POST /bookings` + repository | CURRENTLY IMPLEMENTED (verified Phase 2) |
| Conversation layer + local-test routes | CURRENTLY IMPLEMENTED (verified Phase 3) |
| Conversation manager | PARTIAL (basic flow implemented; buttons/NL routing future) |
| Gemini AI layer | PLANNED / FUTURE |
| Excel integration | PLANNED / FUTURE |
| Google Calendar integration | PLANNED / FUTURE |
| Facebook Messenger | PLANNED / FUTURE |
| Human escalation | PLANNED / FUTURE |
| Reporting / notifications | PLANNED / FUTURE |
