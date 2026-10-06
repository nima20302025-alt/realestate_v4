# -*- coding: utf-8 -*-
"""
Postgres (Supabase) connection handling and schema management.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

import psycopg2
import psycopg2.extras

import config
from config import require_database_url

logger = logging.getLogger(__name__)

# RealDictCursor so rows behave like dicts
psycopg2.extras.register_uuid()


@contextmanager
def get_connection() -> Iterator[psycopg2.extensions.connection]:
    """Yield a Postgres connection; commit on success, rollback on error."""
    url = require_database_url()
    try:
        conn = psycopg2.connect(url, connect_timeout=30)
    except Exception as exc:
        # Hide password in any printed URL fragment
        safe = url.split("@")[-1] if "@" in url else "(url)"
        raise RuntimeError(
            f"Could not connect to Supabase Postgres ({safe}).\n"
            f"Original error: {exc}\n"
            "Checklist:\n"
            "  1) Secret DATABASE_URL is set and cell #3 re-run\n"
            "  2) Password is correct (URL-encode special chars like @ # %)\n"
            "  3) Use Session pooler URI (port 5432) or Transaction (6543)\n"
            "  4) Supabase → Database → Network: allow your IP / 0.0.0.0/0 for Colab"
        ) from exc
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS properties (
        property_id TEXT PRIMARY KEY,
        city TEXT NOT NULL,
        neighborhood TEXT NOT NULL,
        property_type TEXT NOT NULL,
        listing_type TEXT NOT NULL,
        price INTEGER NOT NULL,
        bedrooms INTEGER NOT NULL,
        bathrooms INTEGER NOT NULL,
        area_sqft INTEGER NOT NULL,
        parking INTEGER NOT NULL DEFAULT 0,
        furnished INTEGER NOT NULL DEFAULT 0,
        balcony INTEGER NOT NULL DEFAULT 0,
        garden INTEGER NOT NULL DEFAULT 0,
        pool INTEGER NOT NULL DEFAULT 0,
        elevator INTEGER NOT NULL DEFAULT 0,
        pet_friendly INTEGER NOT NULL DEFAULT 0,
        near_metro INTEGER NOT NULL DEFAULT 0,
        year_built INTEGER,
        property_condition TEXT,
        description TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_properties_city ON properties(city)",
    "CREATE INDEX IF NOT EXISTS idx_properties_type ON properties(property_type)",
    "CREATE INDEX IF NOT EXISTS idx_properties_listing ON properties(listing_type)",
    "CREATE INDEX IF NOT EXISTS idx_properties_price ON properties(price)",
    """
    CREATE TABLE IF NOT EXISTS customers (
        customer_id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS preferences (
        id SERIAL PRIMARY KEY,
        customer_id INTEGER NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
        key TEXT NOT NULL,
        value TEXT,
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_preferences_customer ON preferences(customer_id)",
    """
    CREATE TABLE IF NOT EXISTS taste_insights (
        id SERIAL PRIMARY KEY,
        customer_id INTEGER NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
        insight TEXT NOT NULL,
        source_property_id TEXT,
        source_action TEXT,
        reason TEXT,
        weight REAL NOT NULL DEFAULT 1.0,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_taste_customer ON taste_insights(customer_id)",
    """
    CREATE TABLE IF NOT EXISTS conversations (
        id SERIAL PRIMARY KEY,
        customer_id INTEGER NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
        role TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_conversations_customer ON conversations(customer_id)",
    """
    CREATE TABLE IF NOT EXISTS appointments (
        appointment_id SERIAL PRIMARY KEY,
        customer_id INTEGER NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
        property_id TEXT NOT NULL REFERENCES properties(property_id),
        appointment_date TEXT NOT NULL,
        appointment_time TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'scheduled',
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_appointments_customer ON appointments(customer_id)",
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_appointments_slot
    ON appointments(property_id, appointment_date, appointment_time)
    WHERE status = 'scheduled'
    """,
    """
    CREATE TABLE IF NOT EXISTS property_interactions (
        id SERIAL PRIMARY KEY,
        customer_id INTEGER NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
        property_id TEXT NOT NULL REFERENCES properties(property_id),
        action TEXT NOT NULL,
        reason TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_interactions_customer ON property_interactions(customer_id)",
    "ALTER TABLE appointments ADD COLUMN IF NOT EXISTS notes TEXT",
    "ALTER TABLE customers ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE customers ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT FALSE",
    """
    CREATE TABLE IF NOT EXISTS auth_codes (
        id SERIAL PRIMARY KEY,
        contact TEXT NOT NULL,
        channel TEXT NOT NULL,
        code_hash TEXT NOT NULL,
        attempts INTEGER NOT NULL DEFAULT 0,
        used BOOLEAN NOT NULL DEFAULT FALSE,
        expires_at TIMESTAMPTZ NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_auth_codes_contact ON auth_codes(contact, id DESC)",
]

# Tables that hold personal data. Row Level Security is switched on so Supabase's public
# REST API (anon key) can never read them; this app connects as the table owner, which
# bypasses RLS, so nothing changes for the app itself.
PRIVATE_TABLES = (
    "customers", "preferences", "taste_insights", "conversations",
    "appointments", "property_interactions", "auth_codes",
)


def init_db() -> None:
    """Create every table/index if it doesn't already exist. Idempotent."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            for statement in SCHEMA_STATEMENTS:
                cur.execute(statement)
            cur.execute("DELETE FROM auth_codes WHERE created_at < NOW() - INTERVAL '2 days'")
    if config.ENABLE_RLS:
        for table in PRIVATE_TABLES:
            try:
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            except Exception as exc:  # e.g. not the table owner - not fatal
                logger.warning("Could not enable RLS on %s: %s", table, exc)
    logger.info("Database schema ready (Supabase / Postgres)")
