# Especialty Database (Phase 1)

This document explains the Phase 1 database foundation.

> **Status:** Phase 1 foundation implemented in code + SQL.
> **Not complete** until the SQL migration has been applied in Supabase
> and `GET /health/db` has been manually verified with real credentials.

## Why Supabase / PostgreSQL is the source of truth

* All bookings, customers, conversations, and messages live in one
  relational database so business state is consistent.
* Microsoft Excel (later) is only an operational staff view — it reads
  from or mirrors the database, it never replaces it.
* Google Calendar (later) is only a scheduling view — the booking row
  in PostgreSQL decides what is actually booked.
* AI (Gemini, later) will never write directly to tables. It produces
  structured data; deterministic Python code validates it and then
  writes to Supabase. This keeps business-critical decisions testable.

## Tables overview

| Table | Purpose |
| ----- | ------- |
| `customers` | People who book or order. Contact fields are optional at first. |
| `conversations` | One chat thread per customer + channel (Messenger, website, SMS, test). |
| `messages` | Append-only history of a conversation (customer / assistant / staff / system). |
| `packages` | Sellable party packages with a per-person price. |
| `bookings` | **Both** event bookings (`EVENT`) and food orders (`FOOD_ORDER`). |
| `booking_items` | Line items belonging to a booking (dishes, trays, package charges). |
| `business_settings` | Single-row configuration, e.g. `max_events_per_day = 2`. |

Migration file: `database/migrations/001_initial_schema.sql`

## Why one `bookings` table for events and food orders?

Events and food orders share most fields: customer, status, payment,
price estimate, timestamps. Splitting them into two tables would
duplicate that logic and make reporting (“all revenue this week”)
harder.

* `booking_type` distinguishes them: `EVENT` vs `FOOD_ORDER`.
* `service_type` describes the actual service: `catering`, `food_trays`,
  `party_package`, `individual_food_order`.
* A `FOOD_ORDER` often has no event date, time, location, guest count,
  or package — so those columns stay nullable.
* A future Phase 2 booking engine will require event fields for `EVENT`
  rows in Python code, where the error messages can be user-friendly.

## Why `booking_items` exists separately

A booking is the header (“who, when, how much overall”); items are the
lines (“2 x food tray X, 1 x package Y”).

* One booking can have zero, one, or many items.
* Items keep their own `quantity`, `unit_price`, and `subtotal` so the
  receipt can be reconstructed later even if package prices change.
* The same table works for event catering lines and simple food orders.

## Why money uses NUMERIC, never FLOAT

Floating-point numbers cannot represent decimal money exactly
(e.g. `0.1 + 0.2 != 0.3` in binary floating point). That causes
rounding errors in totals, tax, and reports.

* `packages.price_per_person` is `NUMERIC(10, 2)`.
* `bookings.estimated_price`, `booking_items.unit_price` / `subtotal`
  are `NUMERIC(12, 2)`.
* All have `CHECK (... >= 0)` guards.
* Application code should use Python `Decimal`, not `float`, when it
  starts calculating prices in Phase 2.

## Why business rules live in application logic, not only in SQL

Example: `max_events_per_day = 2` (stored in `business_settings`).

Counting “events on date X” depends on context: only `EVENT` rows with
certain statuses (`CONFIRMED`, `AWAITING_CONFIRMATION`, …) should count,
cancelled ones should not, and time-zone / cut-off rules may apply.
That logic is clearer and easier to test in Python than in a database
trigger, and error messages can guide the customer (“that date is full,
try …” or escalate to a human).

The database enforces what it is good at:

* Primary keys, foreign keys, `NOT NULL` where a value must always exist.
* `CHECK` constraints for fixed value sets (statuses, types) and
  non-negative money / positive quantities.
* Indexes for lookups (`customer_id`, `event_date`, `status`, …).

The Phase 2 deterministic booking engine will enforce the rest.

## Nullability decisions

* `customers.name / phone / email / facebook_id`: all **nullable**.
  A customer may first appear with only a Facebook ID or phone number;
  staff fills in the rest later.
* `conversations.customer_id`: **NOT NULL**. Every thread belongs to
  a known customer row (create the customer first, even if sparse).
* `messages.message`: **NOT NULL**. Empty messages are not stored.
* `bookings.event_date / event_time / event_location / guest_count / package_id`:
  **nullable**. Required for `EVENT` by future app validation, optional
  for `FOOD_ORDER` (e.g. a simple takeaway order has no venue).
* `booking_items.item_name / quantity / unit_price / subtotal`:
  **NOT NULL**. A line item without a price or quantity is meaningless.

## ON DELETE behavior (deliberately non-destructive)

* `conversations.customer_id`, `messages.conversation_id`,
  `bookings.customer_id`, `booking_items.booking_id` use
  `ON DELETE RESTRICT`: you cannot delete a customer, conversation, or
  booking while dependent history exists. This prevents accidental loss
  of booking or message history.
* `bookings.package_id` uses `ON DELETE SET NULL`: deleting a package
  keeps the booking row (with its price snapshot) and just clears the
  link. Deactivating (`is_active = false`) is preferred over deleting.

## How the schema supports future integrations

* **Facebook:** `customers.facebook_id` links a Messenger user to a
  customer; `conversations.channel = 'facebook'` separates Messenger
  threads from website / SMS / test threads.
* **Gemini / Conversation Manager:** `conversations.status`
  (`active`, `closed`, `human_handoff`) and `messages.sender`
  (`customer`, `assistant`, `staff`, `system`) record who said what and
  when a human took over. `bookings.status = 'HUMAN_HANDOFF'` marks
  bookings that need staff review.
* **Excel (staff view):** `bookings` + `booking_items` + `customers`
  contain everything a staff spreadsheet needs; Excel will read from
  the database, not the other way around.
* **Google Calendar:** `bookings.event_date / event_time / event_location`
  plus `status` provide the fields a calendar event needs; the booking
  row remains authoritative if the calendar and database ever disagree.

## Applying the migration (manual step)

Phase 1 is not complete until a human runs the SQL in Supabase:

1. Open the Supabase dashboard → your project → **SQL Editor**.
2. Open `database/migrations/001_initial_schema.sql`, copy its contents.
3. Paste into the SQL Editor and run it once.
4. Verify: `SELECT * FROM business_settings;` should return one row
   (`Especialty`, `2`).

No seed customers, conversations, or bookings are created — only the
single `business_settings` row.

## Verifying the connection (manual step)

1. Copy `.env.example` to `.env` and fill in `SUPABASE_URL` and
   `SUPABASE_SERVICE_ROLE_KEY` (Project Settings → API). Never commit `.env`.
2. Start the API: `uvicorn app.main:app --reload`.
3. `GET http://127.0.0.1:8000/health` → `{"status": "ok"}` (unchanged).
4. `GET http://127.0.0.1:8000/health/db` → `{"status": "ok", "database": "connected"}`.
5. Without credentials it returns 503 `not_configured`; with wrong
   credentials or no network it returns 503 `unavailable` (no key leaked).
