-- Especialty Phase 1: initial schema (PostgreSQL / Supabase compatible).
--
-- How to apply: run this file once in the Supabase SQL Editor
-- (see docs/database.md). It is idempotent where practical
-- (uses IF NOT EXISTS).
--
-- Design notes:
-- * UUID primary keys via gen_random_uuid() (pgcrypto).
-- * TIMESTAMPTZ for all timestamps.
-- * TEXT + CHECK constraints instead of native ENUM types so new
--   channel/status values can be added without a type migration.
-- * NUMERIC for all money fields (never FLOAT).
-- * ON DELETE is deliberately non-destructive: history tables use
--   RESTRICT so a customer/conversation/booking cannot be deleted
--   while dependent rows exist. bookings.package_id uses SET NULL
--   so removing a package never deletes bookings.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Shared trigger to keep updated_at fresh on UPDATE.
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ------------------------------------------------------------------
-- 1. customers
-- ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS customers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  -- All contact fields are nullable: a customer may first appear with
  -- only a facebook_id or a phone number (see docs/database.md).
  name TEXT,
  phone TEXT,
  email TEXT,
  facebook_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers (phone);
CREATE INDEX IF NOT EXISTS idx_customers_email ON customers (email);
CREATE INDEX IF NOT EXISTS idx_customers_facebook_id ON customers (facebook_id);

DROP TRIGGER IF EXISTS trg_customers_updated_at ON customers;
CREATE TRIGGER trg_customers_updated_at
  BEFORE UPDATE ON customers
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ------------------------------------------------------------------
-- 2. conversations
-- ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS conversations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_id UUID NOT NULL REFERENCES customers (id) ON DELETE RESTRICT,
  channel TEXT NOT NULL DEFAULT 'local_test'
    CONSTRAINT chk_conversations_channel
    CHECK (channel IN ('facebook', 'website', 'sms', 'local_test')),
  status TEXT NOT NULL DEFAULT 'active'
    CONSTRAINT chk_conversations_status
    CHECK (status IN ('active', 'closed', 'human_handoff')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_customer_id ON conversations (customer_id);
CREATE INDEX IF NOT EXISTS idx_conversations_status ON conversations (status);
CREATE INDEX IF NOT EXISTS idx_conversations_channel ON conversations (channel);

DROP TRIGGER IF EXISTS trg_conversations_updated_at ON conversations;
CREATE TRIGGER trg_conversations_updated_at
  BEFORE UPDATE ON conversations
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ------------------------------------------------------------------
-- 3. messages
-- ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID NOT NULL REFERENCES conversations (id) ON DELETE RESTRICT,
  sender TEXT NOT NULL
    CONSTRAINT chk_messages_sender
    CHECK (sender IN ('customer', 'assistant', 'staff', 'system')),
  message TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
  -- No updated_at: message history is append-only, never edited.
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_created
  ON messages (conversation_id, created_at);

-- ------------------------------------------------------------------
-- 4. packages
-- ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS packages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL UNIQUE,
  description TEXT,
  price_per_person NUMERIC(10, 2) NOT NULL
    CONSTRAINT chk_packages_price_non_negative CHECK (price_per_person >= 0),
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_packages_is_active ON packages (is_active);

DROP TRIGGER IF EXISTS trg_packages_updated_at ON packages;
CREATE TRIGGER trg_packages_updated_at
  BEFORE UPDATE ON packages
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ------------------------------------------------------------------
-- 5. bookings (both EVENT bookings and FOOD_ORDER records)
-- ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bookings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_id UUID NOT NULL REFERENCES customers (id) ON DELETE RESTRICT,
  booking_type TEXT NOT NULL
    CONSTRAINT chk_bookings_booking_type
    CHECK (booking_type IN ('EVENT', 'FOOD_ORDER')),
  service_type TEXT
    CONSTRAINT chk_bookings_service_type
    CHECK (service_type IN ('catering', 'food_trays', 'party_package', 'individual_food_order')),
  -- Nullable by design: FOOD_ORDER rows may not have event details.
  -- EVENT rows will be validated by the Phase 2 deterministic booking
  -- engine, not by NOT NULL constraints here.
  event_date DATE,
  event_time TIME,
  event_location TEXT,
  guest_count INTEGER CONSTRAINT chk_bookings_guest_count CHECK (guest_count IS NULL OR guest_count > 0),
  package_id UUID REFERENCES packages (id) ON DELETE SET NULL,
  estimated_price NUMERIC(12, 2)
    CONSTRAINT chk_bookings_estimated_price CHECK (estimated_price IS NULL OR estimated_price >= 0),
  status TEXT NOT NULL DEFAULT 'PENDING'
    CONSTRAINT chk_bookings_status
    CHECK (status IN ('PENDING', 'AWAITING_CONFIRMATION', 'CONFIRMED', 'CANCELLED', 'COMPLETED', 'HUMAN_HANDOFF')),
  payment_status TEXT NOT NULL DEFAULT 'UNPAID'
    CONSTRAINT chk_bookings_payment_status
    CHECK (payment_status IN ('UNPAID', 'PENDING', 'PARTIAL', 'PAID', 'REFUNDED')),
  special_requests TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bookings_customer_id ON bookings (customer_id);
CREATE INDEX IF NOT EXISTS idx_bookings_event_date ON bookings (event_date);
CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings (status);
CREATE INDEX IF NOT EXISTS idx_bookings_booking_type ON bookings (booking_type);
CREATE INDEX IF NOT EXISTS idx_bookings_package_id ON bookings (package_id);

DROP TRIGGER IF EXISTS trg_bookings_updated_at ON bookings;
CREATE TRIGGER trg_bookings_updated_at
  BEFORE UPDATE ON bookings
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ------------------------------------------------------------------
-- 6. booking_items
-- ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS booking_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  booking_id UUID NOT NULL REFERENCES bookings (id) ON DELETE RESTRICT,
  item_name TEXT NOT NULL,
  quantity INTEGER NOT NULL DEFAULT 1
    CONSTRAINT chk_booking_items_quantity CHECK (quantity > 0),
  unit_price NUMERIC(12, 2) NOT NULL
    CONSTRAINT chk_booking_items_unit_price CHECK (unit_price >= 0),
  subtotal NUMERIC(12, 2) NOT NULL
    CONSTRAINT chk_booking_items_subtotal CHECK (subtotal >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
  -- No updated_at: line items are immutable history; corrections
  -- create new rows rather than editing in place.
);

CREATE INDEX IF NOT EXISTS idx_booking_items_booking_id ON booking_items (booking_id);

-- ------------------------------------------------------------------
-- 7. business_settings
-- ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS business_settings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_name TEXT NOT NULL,
  max_events_per_day INTEGER NOT NULL DEFAULT 2
    CONSTRAINT chk_business_settings_max_events CHECK (max_events_per_day > 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_business_settings_updated_at ON business_settings;
CREATE TRIGGER trg_business_settings_updated_at
  BEFORE UPDATE ON business_settings
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Initial configuration used by the future deterministic booking engine.
-- Guarded so re-running the migration does not create duplicates.
INSERT INTO business_settings (business_name, max_events_per_day)
SELECT 'Especialty', 2
WHERE NOT EXISTS (SELECT 1 FROM business_settings WHERE business_name = 'Especialty');
