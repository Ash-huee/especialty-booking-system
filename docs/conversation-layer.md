# Conversation Layer (Phase 3)

> **Status:** Phase 3 conversation + messaging foundation implemented,
> automated-tested, AND manually verified against the real Supabase
> database (see `docs/development-log.md`). No Gemini, channels,
> Excel, Calendar, SMS, auth, or payments exist.

## Purpose

Give Gemini (future) and external channels (future) a persisted place to
talk to customers, without letting them touch booking decisions. The
conversation layer stores **who said what, in which thread**; the Phase 2
booking engine alone decides whether a booking is valid.

## Architecture

```text
POST /conversations/messages (thin route)
  ↓ ConversationMessageRequest (shape only)
ConversationManager.handle_customer_message (orchestrates, decides nothing
about bookings)
  ↓ via repository
ConversationRepository (Supabase only, no rules)
  ↓
Supabase/PostgreSQL: customers, conversations, messages (source of truth)

GET /conversations/{id} → metadata + oldest-first history (for testing)
```

* **Models** (`app/models/conversation.py`): channel/status/sender constants
  matching the Phase 1 database contract (lowercase), request shape, results.
* **Services**: `conversation_service.py` (lifecycle), `message_service.py`
  (append + ordered history), `conversation_manager.py` (the 6-step
  local-test flow), `customer_service.py` (shared phone → email → create
  resolution, also used by the booking engine).
* **Routes** (`app/api/routes/conversations.py`): HTTP mapping only
  (201 / 422 / 404 / 503).

## Conversation lifecycle

Statuses are exactly the database values: `active`, `closed`,
`human_handoff` (uppercase ACTIVE/CLOSED/HUMAN_HANDOFF in planning docs
mean these). Transitions are deterministic:

* `active` → `closed`, `active` → `human_handoff`
* `human_handoff` → `active` (reopen), `human_handoff` → `closed`
* `closed` → nothing: closed is terminal. A later message opens a **new**
  active conversation instead of resurrecting the old one.

## Message lifecycle

`store → list oldest-first`. Rows are append-only (no `updated_at`);
nothing edits or deletes. Incoming local-test messages are stored with
sender `customer`. `staff` and `system` senders are supported for future
staff tooling; `assistant` is reserved in the schema for future Gemini
replies and is never produced here.

## Local test API

* `POST /conversations/messages` with `customer_name`, `customer_phone`,
  optional `customer_email`, `channel` (`local_test` only — `facebook` and
  friends are rejected with `UNSUPPORTED_CHANNEL`), and `message`.
  → 201 `{status, conversation_id, customer_id, message_id,
  conversation_status, created_new_conversation, created_new_customer}`;
  422 structured validation; 503 when unconfigured or the database fails.
* `GET /conversations/{conversation_id}` → 200 conversation metadata plus
  messages oldest-first; 404 when unknown; 503 on database failure.

## What Phase 3 does NOT implement

Gemini, message understanding, intent inference, booking creation from
chat, Facebook/SMS/website channels, Excel, Calendar, n8n, chatbot
logic, auth, payments, confirmation flow. The manager deliberately stops
after storing the customer message.

## Relationship to the Phase 2 booking engine

The layers share only the customer-resolution rule (one helper,
`customer_service.find_or_create_customer`) and the `ValidationError`
shape. The conversation layer never imports booking validation, capacity,
or pricing; the booking engine never imports conversations. Gemini will
sit between them: read history here, write a `BookingCreateRequest`
there — with the engine validating everything again.

## Future Gemini integration point

`GET /conversations/{id}` history is the context Gemini will read;
`ConversationMessageRequest` is the shape channel webhooks will map into.
No code for either exists yet.

## Known limitations

* No multi-table transaction (same Supabase REST constraint as Phase 2):
  everything validatable is checked before any write; writes run
  customer → conversation → message, and a mid-flow DB failure returns a
  generic 503 error rather than a partial success.
* One active conversation per customer+channel (newest wins); no
  multi-thread or topic support.
* `customer_email` remains a non-nullable request-model string (inherited
  Phase 2 review item).
