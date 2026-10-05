# Booking Engine (Phase 2)

> **Status:** Phase 2 deterministic engine implemented AND manually verified
> against the real Supabase database (see `docs/development-log.md`).
> No AI, channels, or calendar/Excel work exists.

## Deterministic architecture

```text
POST /bookings (thin route)
  ↓ BookingCreateRequest (structure only)
BookingService.create_booking (decides everything)
  ↓ reads via repository
SupabaseBookingRepository (Supabase only, no rules)
  ↓
Supabase/PostgreSQL (source of truth)
```

* **Models** (`app/models/`): request shapes + normalization. No decisions.
* **Services** (`app/services/`): all business rules. No Supabase calls except
  through the repository object passed in (real in production, fake in tests).
* **Integrations** (`app/integrations/`): Supabase I/O + connection. No rules.
* **Routes** (`app/api/routes/bookings.py`): HTTP mapping only (201/422/409/202/503).

## Why AI is not involved in business decisions

Gemini (a later phase) will only turn free text into a `BookingCreateRequest`.
Whether that request is valid — availability, prices, statuses — is decided
here in plain Python so behavior is predictable, testable, and auditable.
AI output is always validated; it can never confirm a booking by itself.

## Supported booking types

| Type | Requires | Ignores |
| ---- | -------- | ------- |
| `EVENT` | customer name + phone, service_type, event_date, event_time, event_location, guest_count > 0 | — (items optional, validated when present) |
| `FOOD_ORDER` | customer name + phone, service_type, ≥1 booking item | event_date/time/location, guest_count |

`booking_type` is normalized case-insensitively (`event` → `EVENT`);
`service_type` must be exactly one of `catering`, `food_trays`,
`party_package`, `individual_food_order` — anything else is rejected,
never converted.

## Validation rules (all deterministic)

Customer (both types): name/phone required after trimming; email optional
but format-checked (`user@domain.tld` shape, no spaces) when supplied.

EVENT: date, time, location, guest_count required; guest_count > 0.
FOOD_ORDER: ≥1 item; each item needs a non-blank name, quantity > 0,
unit_price ≥ 0. EVENT items, when supplied, follow the same item rules.

General: unknown booking/service types rejected; supplied `estimated_price`
must be ≥ 0 (the engine recomputes the authoritative price anyway);
`package_id` must be a valid UUID of an existing **active** package when
provided (`PACKAGE_NOT_FOUND` / `PACKAGE_INACTIVE`).

Errors are structured: `{field, code, message}`, e.g.
`{field: "guest_count", code: "INVALID_GUEST_COUNT",
message: "Guest count must be greater than zero."}` — never "Invalid request."

## Capacity rule

`business_settings.max_events_per_day` is read from Supabase on every EVENT
request — the value `2` appears nowhere in Python code.

1. Query bookings where `booking_type = EVENT`, `event_date = <date>`,
   `status != CANCELLED` (food orders never consume event slots).
2. If count ≥ limit, reject with `EVENT_CAPACITY_REACHED` and store nothing.
3. Any settings/capacity DB failure → `HUMAN_HANDOFF`, never a guess.

## Pricing logic (Decimal only)

* EVENT with a package: `guest_count × package.price_per_person`
  (package row is the price source; Python never invents prices).
* EVENT without a package: price stays `null` (still a valid booking).
* FOOD_ORDER: `sum(quantity × unit_price)` over items.
* All math uses `Decimal` quantized to cents; JSON/DB transport uses
  strings (`"102.00"`) so no float error and no `Decimal` serialization crash.

## Customer matching (deterministic, no AI)

1. Exact phone match → reuse that customer.
2. Else exact email match (when an email was supplied) → reuse.
3. Else create one new customer row.

No fuzzy matching. Whitespace is trimmed before comparing/storing.

## Booking lifecycle and statuses

* Every stored booking starts as `status = PENDING`, `payment_status = UNPAID`.
* The engine never writes `CONFIRMED` — confirmation is a future explicit
  operation. Invalid requests store nothing and are never confirmed.
* `HUMAN_HANDOFF` (booking or conversation level) means staff must decide:
  unexpected DB state, unwritable records, or anything unsafe to automate.
  Item-write failure after the booking row exists returns a handoff that
  **includes the booking_id** so staff can reconcile (see limitations).

## Human handoff behavior

HTTP `202` with `{status: "human_handoff", booking_status: "HUMAN_HANDOFF",
message: <staff-safe sentence>}`. Messages never contain internals or keys.
Unexpected exceptions in the route also map to this shape (logged server-side).

## Transaction / partial-write safety (known limitation)

The Supabase REST client used here has no multi-table transaction, so the
service does **not** claim atomicity:

* Everything checkable is validated **before** any write.
* Write order is customer → booking → items (dependency order).
* If item insertion fails after the booking row exists, the booking remains
  and the response is a handoff carrying its id — documented, not silent.
* A future phase should add a Postgres function / RPC performing all three
  inserts atomically, plus staff cleanup tooling for orphans.

## Testing strategy

* Unit tests use `tests/fakes.py` (`FakeBookingRepository`) — no credentials:
  `test_pricing_service`, `test_booking_validation`, `test_booking_capacity`,
  `test_booking_customer_status`, `test_bookings_api`.
* Repository query test asserts the capacity filter
  (`booking_type = EVENT`, `event_date = …`, `status != CANCELLED`).
* Live test `tests/test_booking_integration.py` is skipped without credentials
  and performs a real FOOD_ORDER write + FK-safe cleanup when configured.

## No schema change in Phase 2

`001_initial_schema.sql` already stores everything the engine needs, so **no
`002` migration was created**. A future phase adds one only for genuinely new
requirements (e.g. atomic-write RPC, confirmation audit columns).

## Manual verification (against real Supabase — Phase 2 complete)

* Valid EVENT → 201, persisted with status PENDING.
* Invalid EVENT (missing/null `event_location`) → 422, no booking or
  customer record created.
* Capacity on one date: first EVENT → 201, second EVENT → 201,
  third EVENT → 409 `EVENT_CAPACITY_REACHED`, third booking not created.
* Valid FOOD_ORDER → 201 with correct Decimal total (verified: 2 × 150 +
  3 × 100 = 600.00; and 3 × 125.50 + 2 × 249.75 = 876.00), persisted.
* FOOD_ORDER with no items → 422 `REQUIRED_BOOKING_ITEMS`, nothing created.
* FOOD_ORDER with quantity 0 → 422 `INVALID_ITEM_QUANTITY`, nothing created.
* FOOD_ORDER with negative unit_price → 422 `INVALID_ITEM_PRICE`, nothing created.
* Customer matching verified live: existing customer reused by phone, reused
  by email with a different phone, and a genuinely new customer created —
  no duplicates in any case.
* Request-model correction found during verification: `event_location` and
  `special_requests` now accept null at the Pydantic layer (FOOD_ORDER
  carries no event details); the service still requires `event_location`
  for EVENT. `customer_email` intentionally remains a non-nullable string
  for minimal scope (review item).

## Implemented vs. future

IMPLEMENTED: models, pricing, validation, capacity, customer matching,
repository, `POST /bookings`, handoff, unit tests, live-test stub.
FUTURE: Gemini extraction, Messenger/SMS/website, Excel, Calendar, n8n,
chatbot logic, auth, payments, confirmation flow, reporting.
