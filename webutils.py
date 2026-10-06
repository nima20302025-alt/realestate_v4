# -*- coding: utf-8 -*-
"""
Pure helpers for the web layer (no FastAPI / DB imports, so they are easy to unit-test).
"""
from __future__ import annotations

import re
import urllib.parse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

SLOT_TIMES: List[str] = [f"{h:02d}:00" for h in range(9, 18)]
AMENITY_KEYS = (
    "parking",
    "garden",
    "near_metro",
    "pool",
    "balcony",
    "elevator",
    "pet_friendly",
    "furnished",
)
MAX_BOOKING_DAYS_AHEAD = 180


def _int(v: Any) -> Optional[int]:
    try:
        if v is None or v == "":
            return None
        return int(v)
    except (TypeError, ValueError):
        return None


# ── property shaping ─────────────────────────────────────────────────────────


def extract_address(description: Optional[str]) -> Dict[str, Optional[str]]:
    """Pull street + 'WA 98133' out of the description written by the CSV importer."""
    text = description or ""
    street = None
    m = re.search(r"Address:\s*([^.]+)\.", text)
    if m:
        street = m.group(1).strip() or None
    statezip = None
    m = re.search(r"\(([A-Z]{2}\s*\d{5})\)", text)
    if m:
        statezip = m.group(1).strip()
    return {"street": street, "statezip": statezip}


def full_address(prop: Dict[str, Any]) -> Optional[str]:
    parts = extract_address(prop.get("description"))
    if not parts["street"]:
        return None
    bits = [parts["street"], prop.get("city") or ""]
    tail = parts["statezip"] or "WA"
    return ", ".join(b for b in bits if b) + f", {tail}"


def maps_url(query: Optional[str]) -> Optional[str]:
    if not query:
        return None
    return "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(query)


def to_card(
    p: Dict[str, Any],
    match_score: Optional[float] = None,
    desc_len: Optional[int] = 240,
) -> Dict[str, Any]:
    price = _int(p.get("price"))
    area = _int(p.get("area_sqft"))
    desc = p.get("description") or ""
    if desc_len is not None:
        desc = desc[:desc_len]
    addr = full_address(p)
    card: Dict[str, Any] = {
        "property_id": p.get("property_id"),
        "city": p.get("city"),
        "neighborhood": p.get("neighborhood"),
        "property_type": p.get("property_type"),
        "listing_type": p.get("listing_type"),
        "price": price,
        "bedrooms": _int(p.get("bedrooms")),
        "bathrooms": _int(p.get("bathrooms")),
        "area_sqft": area,
        "price_per_sqft": round(price / area) if price and area else None,
        "year_built": _int(p.get("year_built")),
        "property_condition": p.get("property_condition"),
        "match_score": match_score if match_score is not None else p.get("match_score"),
        "address": addr,
        "maps_url": maps_url(addr or (f"{p.get('neighborhood')}, {p.get('city')}, WA" if p.get("city") else None)),
        "description": desc,
    }
    for key in AMENITY_KEYS:
        card[key] = bool(p.get(key))
    return card


def pct_vs(value: Optional[float], baseline: Optional[float]) -> Optional[float]:
    if value is None or not baseline:
        return None
    return round((value / baseline - 1) * 100, 1)


def compare_winners(cards: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Which listing wins each metric (ties -> several ids) and an overall pick."""

    def pick(key: str, better) -> Optional[List[str]]:
        vals = [(c[key], c["property_id"]) for c in cards if c.get(key) is not None]
        if len(vals) < 2:
            return None
        best = better(v for v, _ in vals)
        winners = [pid for v, pid in vals if v == best]
        # everybody tied -> nobody "wins"
        return None if len(winners) == len(vals) else winners

    result: Dict[str, Any] = {
        "price": pick("price", min),
        "price_per_sqft": pick("price_per_sqft", min),
        "area_sqft": pick("area_sqft", max),
        "year_built": pick("year_built", max),
        "bedrooms": pick("bedrooms", max),
    }
    wins: Counter = Counter()
    for ids in result.values():
        for pid in ids or []:
            wins[pid] += 1
    overall = None
    if wins:
        top = max(wins.values())
        leaders = [c for c in cards if wins.get(c["property_id"]) == top]
        leaders.sort(key=lambda c: (c.get("price_per_sqft") or 10**9, c.get("price") or 10**12))
        overall = leaders[0]["property_id"]
    result["overall"] = overall
    result["wins"] = dict(wins)
    return result


# ── appointments ─────────────────────────────────────────────────────────────


def parse_slot(date_s: str, time_s: str, today: Optional[date] = None) -> date:
    """Validate a viewing date/time. Raises ValueError with a user-facing message."""
    today = today or datetime.now(timezone.utc).date()
    try:
        d = datetime.strptime(date_s, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ValueError("Date must look like 2026-10-15.")
    if time_s not in SLOT_TIMES:
        raise ValueError("Viewings start on the hour between 09:00 and 17:00.")
    # one day of slack: the server runs on UTC, the visitor may be hours behind
    if d < today - timedelta(days=1):
        raise ValueError("That date is in the past.")
    if d > today + timedelta(days=MAX_BOOKING_DAYS_AHEAD):
        raise ValueError("Viewings can be booked up to 6 months ahead.")
    return d


def shape_appointment(row: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(row)
    addr = full_address(row)
    out["address"] = addr
    out["maps_url"] = maps_url(addr or (f"{row.get('neighborhood')}, {row.get('city')}, WA" if row.get("city") else None))
    out.pop("description", None)
    return out


def _ics_escape(text: Any) -> str:
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r", "")
        .replace("\n", "\\n")
    )


def build_ics(appt: Dict[str, Any], now: Optional[datetime] = None) -> str:
    """One-hour calendar event (floating local time) for a viewing."""
    now = now or datetime.now(timezone.utc)
    day = datetime.strptime(str(appt["appointment_date"]), "%Y-%m-%d")
    hh, mm = (int(x) for x in str(appt["appointment_time"]).split(":")[:2])
    start = day.replace(hour=hh, minute=mm)
    end = start + timedelta(hours=1)
    fmt = "%Y%m%dT%H%M%S"

    kind = appt.get("property_type") or "Home"
    where = ", ".join(x for x in (appt.get("neighborhood"), appt.get("city")) if x)
    title = f"Viewing: {kind} in {where}" if where else f"Viewing: {appt.get('property_id')}"
    desc_lines = [f"Property {appt.get('property_id')}"]
    if appt.get("price"):
        desc_lines.append(f"Listed at ${int(appt['price']):,}")
    if appt.get("notes"):
        desc_lines.append(f"Notes: {appt['notes']}")
    location = appt.get("address") or where

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//LuxeHome//Viewing//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:viewing-{appt.get('appointment_id')}@luxehome",
        f"DTSTAMP:{now.strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART:{start.strftime(fmt)}",
        f"DTEND:{end.strftime(fmt)}",
        f"SUMMARY:{_ics_escape(title)}",
        f"DESCRIPTION:{_ics_escape(chr(10).join(desc_lines))}",
    ]
    if location:
        lines.append(f"LOCATION:{_ics_escape(location)}")
    lines += [
        "BEGIN:VALARM",
        "TRIGGER:-PT1H",
        "ACTION:DISPLAY",
        "DESCRIPTION:Viewing in 1 hour",
        "END:VALARM",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(lines) + "\r\n"
