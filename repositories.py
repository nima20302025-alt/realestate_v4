# -*- coding: utf-8 -*-
"""
Data access layer for Postgres / Supabase. Parameterized SQL only.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import psycopg2.extras

from database import get_connection

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Properties
# --------------------------------------------------------------------------

_ORDER_BY = {
    "price_asc": "price ASC, property_id",
    "price_desc": "price DESC, property_id",
    "area_desc": "area_sqft DESC, property_id",
    "newest": "year_built DESC NULLS LAST, property_id",
}

_FLAGS = (
    "parking",
    "furnished",
    "balcony",
    "garden",
    "pool",
    "elevator",
    "pet_friendly",
    "near_metro",
)


def _build_where(requirements: Dict[str, Any]) -> Tuple[str, List[Any]]:
    """Shared WHERE clause for search + count (parameterized)."""
    clauses: List[str] = ["1=1"]
    params: List[Any] = []

    # Case-insensitive text filters (dataset cities: Seattle, Bellevue, ...)
    if requirements.get("city"):
        clauses.append("LOWER(city) = LOWER(%s)")
        params.append(str(requirements["city"]).strip())
    if requirements.get("listing_type"):
        clauses.append("LOWER(listing_type) = LOWER(%s)")
        params.append(str(requirements["listing_type"]).strip())
    if requirements.get("property_type"):
        clauses.append("LOWER(property_type) = LOWER(%s)")
        params.append(str(requirements["property_type"]).strip())
    if requirements.get("neighborhood"):
        clauses.append("LOWER(neighborhood) LIKE LOWER(%s)")
        params.append(f"%{str(requirements['neighborhood']).strip()}%")

    if requirements.get("bedrooms"):
        clauses.append("bedrooms >= %s")
        params.append(requirements["bedrooms"])
    if requirements.get("bathrooms"):
        clauses.append("bathrooms >= %s")
        params.append(requirements["bathrooms"])
    if requirements.get("min_area_sqft"):
        clauses.append("area_sqft >= %s")
        params.append(requirements["min_area_sqft"])
    if requirements.get("budget_minimum"):
        clauses.append("price >= %s")
        params.append(requirements["budget_minimum"])

    budget = requirements.get("budget_absolute_max") or requirements.get("budget_preferred")
    if budget:
        clauses.append("price <= %s")
        params.append(budget)

    for flag in _FLAGS:
        if requirements.get(flag):
            clauses.append(f"{flag} = 1")

    return " AND ".join(clauses), params


def search_properties(
    requirements: Dict[str, Any], limit: int = 100, order_by: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Filter the properties table by whatever criteria are present."""
    where, params = _build_where(requirements)
    query = f"SELECT * FROM properties WHERE {where}"
    order_sql = _ORDER_BY.get(order_by or "")
    if order_sql:
        query += f" ORDER BY {order_sql}"
    query += " LIMIT %s"
    params.append(limit)

    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]


def count_properties(requirements: Dict[str, Any]) -> int:
    where, params = _build_where(requirements)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM properties WHERE {where}", params)
            return int(cur.fetchone()[0])


def get_market_meta() -> Dict[str, Any]:
    """Cities, price range, property types and which amenity flags actually have data."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT city, COUNT(*) AS n FROM properties GROUP BY city ORDER BY n DESC, city")
            cities = [{"city": r["city"], "n": int(r["n"])} for r in cur.fetchall()]
            cur.execute("SELECT MIN(price) AS min_price, MAX(price) AS max_price, COUNT(*) AS total FROM properties")
            rng = dict(cur.fetchone() or {})
            cur.execute("SELECT DISTINCT property_type FROM properties ORDER BY property_type")
            types = [r["property_type"] for r in cur.fetchall()]
            cur.execute(
                "SELECT " + ", ".join(f"COALESCE(SUM({f}), 0) AS {f}" for f in _FLAGS) + " FROM properties"
            )
            flags = {k: int(v or 0) for k, v in dict(cur.fetchone() or {}).items()}
    return {
        "cities": cities,
        "min_price": rng.get("min_price"),
        "max_price": rng.get("max_price"),
        "total": int(rng.get("total") or 0),
        "types": types,
        "flags": flags,
    }


def get_city_stats(city: str) -> Dict[str, Any]:
    """Average price / price-per-sqft / area for sale listings in a city."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS n,
                       AVG(price)::float AS avg_price,
                       AVG(price::float / NULLIF(area_sqft, 0))::float AS avg_ppsf,
                       AVG(area_sqft)::float AS avg_area
                FROM properties
                WHERE LOWER(city) = LOWER(%s) AND LOWER(listing_type) = 'sale'
                """,
                (city,),
            )
            return dict(cur.fetchone() or {})


def find_similar(prop: Dict[str, Any], limit: int = 4) -> List[Dict[str, Any]]:
    """Same city, similar price (+-15%), bedrooms within 1 - closest price first."""
    price = int(prop.get("price") or 0)
    area = int(prop.get("area_sqft") or 0)
    beds = int(prop.get("bedrooms") or 0)
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT * FROM properties
                WHERE property_id <> %s
                  AND LOWER(city) = LOWER(%s)
                  AND price BETWEEN %s AND %s
                  AND ABS(bedrooms - %s) <= 1
                ORDER BY ABS(price - %s), ABS(area_sqft - %s)
                LIMIT %s
                """,
                (
                    prop["property_id"],
                    prop.get("city") or "",
                    int(price * 0.85),
                    int(price * 1.15),
                    beds,
                    price,
                    area,
                    limit,
                ),
            )
            return [dict(r) for r in cur.fetchall()]


def get_property(property_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM properties WHERE property_id = %s", (property_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def get_properties_by_ids(property_ids: List[str]) -> List[Dict[str, Any]]:
    if not property_ids:
        return []
    placeholders = ",".join(["%s"] * len(property_ids))
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"SELECT * FROM properties WHERE property_id IN ({placeholders})",
                property_ids,
            )
            rows = cur.fetchall()
    by_id = {r["property_id"]: dict(r) for r in rows}
    return [by_id[pid] for pid in property_ids if pid in by_id]


# --------------------------------------------------------------------------
# Customers & preferences
# --------------------------------------------------------------------------


def create_customer(
    name: str, email: Optional[str] = None, phone: Optional[str] = None
) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO customers (name, email, phone)
                VALUES (%s, %s, %s)
                RETURNING customer_id
                """,
                (name, email, phone),
            )
            return cur.fetchone()[0]


def get_customer(customer_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT customer_id, name, email, phone, "
                "COALESCE(phone_verified, FALSE) AS phone_verified, "
                "COALESCE(email_verified, FALSE) AS email_verified "
                "FROM customers WHERE customer_id = %s",
                (customer_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def update_customer(
    customer_id: int, name: Optional[str] = None, phone: Optional[str] = None
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE customers SET name = COALESCE(%s, name), phone = COALESCE(%s, phone) "
                "WHERE customer_id = %s",
                (name, phone, customer_id),
            )


# --- sign-in codes / verified contacts --------------------------------------

_CUSTOMER_TABLES = ("preferences", "taste_insights", "conversations", "appointments", "property_interactions")


def _phone_variants(value: str) -> List[str]:
    digits = value.lstrip("+")
    out = {value, digits}
    if value.startswith("+1") and len(value) == 12:
        out.add(digits[1:])
    return sorted(out)


def find_customer_by_contact(channel: str, value: str) -> Optional[Dict[str, Any]]:
    """Account owning this (normalized) email / phone; verified accounts win."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if channel == "email":
                cur.execute(
                    "SELECT customer_id, name FROM customers WHERE LOWER(email) = %s "
                    "ORDER BY COALESCE(email_verified, FALSE) DESC, customer_id LIMIT 1",
                    (value,),
                )
            else:
                cur.execute(
                    "SELECT customer_id, name FROM customers WHERE phone = ANY(%s) "
                    "ORDER BY COALESCE(phone_verified, FALSE) DESC, customer_id LIMIT 1",
                    (_phone_variants(value),),
                )
            row = cur.fetchone()
            return dict(row) if row else None


def set_customer_contact(customer_id: int, channel: str, value: str) -> None:
    col, flag = ("email", "email_verified") if channel == "email" else ("phone", "phone_verified")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE customers SET {col} = %s, {flag} = TRUE WHERE customer_id = %s",
                (value, customer_id),
            )


def create_verified_customer(name: str, channel: str, value: str) -> int:
    cid = create_customer(name=name)
    set_customer_contact(cid, channel, value)
    return cid


def merge_customers(from_id: int, to_id: int) -> None:
    """Move everything a guest collected before signing in onto the real account."""
    if from_id == to_id:
        return
    with get_connection() as conn:
        with conn.cursor() as cur:
            for table in _CUSTOMER_TABLES:
                cur.execute(
                    f"UPDATE {table} SET customer_id = %s WHERE customer_id = %s", (to_id, from_id)
                )


def store_auth_code(contact: str, channel: str, code_hash: str, ttl_minutes: int = 10) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO auth_codes (contact, channel, code_hash, expires_at) "
                "VALUES (%s, %s, %s, NOW() + (%s || ' minutes')::interval)",
                (contact, channel, code_hash, str(int(ttl_minutes))),
            )


def auth_code_stats(contact: str) -> Dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours'), "
                "EXTRACT(EPOCH FROM (NOW() - MAX(created_at))) FROM auth_codes WHERE contact = %s",
                (contact,),
            )
            sent, since = cur.fetchone()
            return {"sent_24h": int(sent or 0), "seconds_since_last": float(since) if since is not None else None}


def check_auth_code(contact: str, code_hash: str, max_attempts: int = 5) -> str:
    """'ok' | 'bad' | 'expired' | 'locked' for the newest unused code of this contact."""
    import hmac

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, code_hash, attempts, expires_at > NOW() FROM auth_codes "
                "WHERE contact = %s AND used = FALSE ORDER BY id DESC LIMIT 1 FOR UPDATE",
                (contact,),
            )
            row = cur.fetchone()
            if row is None or not row[3]:
                return "expired"
            code_id, stored, attempts, _ = row
            if attempts >= max_attempts:
                return "locked"
            if hmac.compare_digest(stored, code_hash):
                cur.execute("UPDATE auth_codes SET used = TRUE WHERE id = %s", (code_id,))
                return "ok"
            cur.execute("UPDATE auth_codes SET attempts = attempts + 1 WHERE id = %s", (code_id,))
            return "locked" if attempts + 1 >= max_attempts else "bad"


def find_customer_by_phone(phone: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT customer_id, name, email, phone FROM customers WHERE phone = %s",
                (phone,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def save_preference(customer_id: int, key: str, value: Any) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO preferences (customer_id, key, value) VALUES (%s, %s, %s)",
                (customer_id, key, str(value)),
            )


def get_customer_profile(customer_id: int) -> Dict[str, str]:
    """Latest value per preference key (later rows override earlier ones)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT key, value FROM preferences WHERE customer_id = %s ORDER BY id",
                (customer_id,),
            )
            rows = cur.fetchall()
    return {key: value for key, value in rows}


# --------------------------------------------------------------------------
# Favorites (stored as preferences with key "favorite:<property_id>")
# --------------------------------------------------------------------------


def list_favorite_ids(customer_id: int) -> List[str]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT key, MIN(id) AS first_id FROM preferences "
                "WHERE customer_id = %s AND key LIKE %s GROUP BY key ORDER BY first_id",
                (customer_id, "favorite:%"),
            )
            return [row[0].split(":", 1)[1] for row in cur.fetchall()]


def add_favorite(customer_id: int, property_id: str) -> None:
    key = f"favorite:{property_id}"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM preferences WHERE customer_id = %s AND key = %s LIMIT 1",
                (customer_id, key),
            )
            if cur.fetchone() is None:
                cur.execute(
                    "INSERT INTO preferences (customer_id, key, value) VALUES (%s, %s, '1')",
                    (customer_id, key),
                )


def remove_favorite(customer_id: int, property_id: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM preferences WHERE customer_id = %s AND key = %s",
                (customer_id, f"favorite:{property_id}"),
            )


# --------------------------------------------------------------------------
# Taste insights
# --------------------------------------------------------------------------


def save_taste_insight(
    customer_id: int,
    insight: str,
    source_property_id: Optional[str] = None,
    source_action: Optional[str] = None,
    reason: Optional[str] = None,
    weight: float = 1.0,
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO taste_insights
                    (customer_id, insight, source_property_id, source_action, reason, weight)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (customer_id, insight, source_property_id, source_action, reason, weight),
            )


def get_taste_insights(customer_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT insight, source_property_id, source_action, reason, weight, created_at
                FROM taste_insights
                WHERE customer_id = %s
                ORDER BY id DESC
                LIMIT %s
                """,
                (customer_id, limit),
            )
            return [dict(r) for r in cur.fetchall()]


def get_taste_summary(customer_id: int) -> str:
    insights = get_taste_insights(customer_id)
    if not insights:
        return ""
    seen: Dict[str, float] = {}
    for i in insights:
        key = i["insight"].strip().lower()
        seen[key] = max(seen.get(key, 0), float(i["weight"] or 1))
    ranked = sorted(seen.items(), key=lambda x: -x[1])
    return "; ".join(text for text, _ in ranked[:8])


# --------------------------------------------------------------------------
# Conversation history
# --------------------------------------------------------------------------


def save_message(customer_id: int, role: str, message: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO conversations (customer_id, role, message) VALUES (%s, %s, %s)",
                (customer_id, role, message),
            )


def load_history(customer_id: int) -> List[Dict[str, str]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT role, message FROM conversations WHERE customer_id = %s ORDER BY id",
                (customer_id,),
            )
            rows = cur.fetchall()
    return [{"role": r[0], "content": r[1]} for r in rows]


# --------------------------------------------------------------------------
# Appointments
# --------------------------------------------------------------------------


def check_appointment_availability(
    property_id: str, appointment_date: str, appointment_time: str
) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT appointment_id FROM appointments
                WHERE property_id = %s AND appointment_date = %s AND appointment_time = %s
                  AND status = 'scheduled'
                """,
                (property_id, appointment_date, appointment_time),
            )
            return cur.fetchone() is None


def create_appointment(
    customer_id: int,
    property_id: str,
    appointment_date: str,
    appointment_time: str,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    if not check_appointment_availability(property_id, appointment_date, appointment_time):
        return {
            "success": False,
            "appointment_id": None,
            "message": "This time slot is already booked.",
        }

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO appointments
                        (customer_id, property_id, appointment_date, appointment_time, status, notes)
                    VALUES (%s, %s, %s, %s, 'scheduled', %s)
                    RETURNING appointment_id
                    """,
                    (customer_id, property_id, appointment_date, appointment_time, notes),
                )
                appointment_id = cur.fetchone()[0]
    except Exception as exc:
        logger.warning("Failed to book appointment: %s", exc)
        return {
            "success": False,
            "appointment_id": None,
            "message": "This time slot is already booked.",
        }

    return {
        "success": True,
        "appointment_id": appointment_id,
        "message": "Appointment booked successfully.",
    }


def get_customer_appointments(customer_id: int) -> List[Dict[str, Any]]:
    columns = [
        "appointment_id",
        "property_id",
        "appointment_date",
        "appointment_time",
        "status",
        "created_at",
    ]
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT {', '.join(columns)}
                FROM appointments
                WHERE customer_id = %s
                ORDER BY appointment_date, appointment_time
                """,
                (customer_id,),
            )
            return [dict(r) for r in cur.fetchall()]


_APPT_SELECT = """
    SELECT a.appointment_id, a.property_id, a.appointment_date, a.appointment_time,
           a.status, a.notes, a.created_at,
           p.city, p.neighborhood, p.property_type, p.price, p.bedrooms, p.bathrooms,
           p.area_sqft, p.description
    FROM appointments a
    LEFT JOIN properties p ON p.property_id = a.property_id
"""


def get_appointments_detailed(
    customer_id: int, include_history: bool = False
) -> List[Dict[str, Any]]:
    """Appointments joined with their property, one query (no N+1 in the UI)."""
    where = "a.customer_id = %s"
    if not include_history:
        where += " AND a.status = 'scheduled'"
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"{_APPT_SELECT} WHERE {where} ORDER BY a.appointment_date, a.appointment_time",
                (customer_id,),
            )
            return [dict(r) for r in cur.fetchall()]


def get_appointment_detailed(appointment_id: int, customer_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"{_APPT_SELECT} WHERE a.appointment_id = %s AND a.customer_id = %s",
                (appointment_id, customer_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def reschedule_appointment(
    appointment_id: int, customer_id: int, appointment_date: str, appointment_time: str
) -> Dict[str, Any]:
    taken = {"success": False, "message": "This time slot is already booked."}
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT property_id FROM appointments "
                    "WHERE appointment_id = %s AND customer_id = %s AND status = 'scheduled'",
                    (appointment_id, customer_id),
                )
                row = cur.fetchone()
                if row is None:
                    return {"success": False, "message": "Appointment not found or already cancelled."}
                cur.execute(
                    "SELECT 1 FROM appointments WHERE property_id = %s AND appointment_date = %s "
                    "AND appointment_time = %s AND status = 'scheduled' AND appointment_id <> %s",
                    (row[0], appointment_date, appointment_time, appointment_id),
                )
                if cur.fetchone() is not None:
                    return taken
                cur.execute(
                    "UPDATE appointments SET appointment_date = %s, appointment_time = %s "
                    "WHERE appointment_id = %s",
                    (appointment_date, appointment_time, appointment_id),
                )
    except psycopg2.errors.UniqueViolation:
        return taken
    return {"success": True, "appointment_id": appointment_id, "message": "Viewing rescheduled."}


STANDARD_TIME_SLOTS = [f"{h:02d}:00" for h in range(9, 18)]


def get_available_slots(property_id: str, appointment_date: str) -> List[str]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT appointment_time FROM appointments
                WHERE property_id = %s AND appointment_date = %s AND status = 'scheduled'
                """,
                (property_id, appointment_date),
            )
            booked = {r[0] for r in cur.fetchall()}
    return [slot for slot in STANDARD_TIME_SLOTS if slot not in booked]


def cancel_appointment(appointment_id: int, customer_id: int) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE appointments SET status = 'cancelled'
                WHERE appointment_id = %s AND customer_id = %s AND status = 'scheduled'
                """,
                (appointment_id, customer_id),
            )
            return cur.rowcount > 0


# --------------------------------------------------------------------------
# Property interactions
# --------------------------------------------------------------------------


def save_property_interaction(
    customer_id: int, property_id: str, action: str, reason: Optional[str] = None
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO property_interactions (customer_id, property_id, action, reason)
                VALUES (%s, %s, %s, %s)
                """,
                (customer_id, property_id, action, reason),
            )


def get_customer_interactions(customer_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT property_id, action, reason, created_at FROM property_interactions
                WHERE customer_id = %s ORDER BY id DESC
                """,
                (customer_id,),
            )
            return [dict(r) for r in cur.fetchall()]
