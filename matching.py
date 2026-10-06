# -*- coding: utf-8 -*-
"""
Scoring and ranking of candidate properties.

Combines:
- how well a listing matches stated requirements
- boost/penalty from like/reject history
- soft boosts derived from taste insights (e.g. "must have parking")
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from repositories import get_customer_interactions, get_taste_insights

# Keywords in taste insights that map to property flags / soft preferences
_INSIGHT_FLAG_HINTS = {
    "parking": "parking",
    "garage": "parking",
    "pet": "pet_friendly",
    "dog": "pet_friendly",
    "cat": "pet_friendly",
    "metro": "near_metro",
    "subway": "near_metro",
    "transit": "near_metro",
    "garden": "garden",
    "yard": "garden",
    "balcony": "balcony",
    "pool": "pool",
    "elevator": "elevator",
    "furnished": "furnished",
}


def _requirement_match_score(prop: Dict[str, Any], requirements: Dict[str, Any]) -> float:
    score = 0.0

    budget = requirements.get("budget_preferred")
    if budget:
        diff = abs(prop["price"] - budget)
        score += max(0.0, 35 * (1 - diff / budget))

    if requirements.get("bedrooms") and prop["bedrooms"] >= requirements["bedrooms"]:
        score += 25

    if requirements.get("parking") and prop.get("parking"):
        score += 15

    if requirements.get("pet_friendly") and prop.get("pet_friendly"):
        score += 15

    if requirements.get("near_metro") and prop.get("near_metro"):
        score += 10

    if requirements.get("garden") and prop.get("garden"):
        score += 10

    if requirements.get("balcony") and prop.get("balcony"):
        score += 5

    if requirements.get("pool") and prop.get("pool"):
        score += 5

    return score


def _history_adjustment(property_id: str, interactions: List[Dict[str, Any]]) -> float:
    adjustment = 0.0
    for interaction in interactions:
        if interaction["property_id"] != property_id:
            continue
        if interaction["action"] in ("like", "interested"):
            adjustment += 10
        elif interaction["action"] in ("reject", "not_interested"):
            adjustment -= 20
    return adjustment


def _taste_adjustment(prop: Dict[str, Any], insights: List[Dict[str, Any]]) -> float:
    """Soft boost/penalty from free-text taste insights."""
    if not insights:
        return 0.0
    adjustment = 0.0
    for item in insights:
        text = (item.get("insight") or "").lower()
        weight = float(item.get("weight") or 1.0)
        action = (item.get("source_action") or "").lower()
        is_negative = action in ("reject", "not_interested") or any(
            w in text for w in ("avoid", "no ", "don't want", "hate", "dislike", "too ")
        )

        for keyword, flag in _INSIGHT_FLAG_HINTS.items():
            if keyword not in text:
                continue
            has_flag = bool(prop.get(flag))
            if is_negative:
                # They disliked something related to this flag → penalize if present,
                # or slightly boost if absent (they want the opposite)
                if has_flag:
                    adjustment -= 8 * weight
                else:
                    adjustment += 3 * weight
            else:
                if has_flag:
                    adjustment += 8 * weight
                else:
                    adjustment -= 4 * weight

        # Budget sensitivity phrases
        if any(w in text for w in ("expensive", "over budget", "cheaper", "lower price", "too much")):
            # Prefer properties under their preferred/max if we can
            pass  # hard filters already handle budget; soft nudge via score is limited

    return adjustment


def score_properties(
    properties: List[Dict[str, Any]],
    requirements: Dict[str, Any],
    customer_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Return properties sorted by match_score (desc), each annotated with it."""
    interactions = get_customer_interactions(customer_id) if customer_id else []
    insights = get_taste_insights(customer_id) if customer_id else []

    scored = []
    for prop in properties:
        item = dict(prop)
        score = _requirement_match_score(prop, requirements)
        score += _history_adjustment(prop["property_id"], interactions)
        score += _taste_adjustment(prop, insights)
        item["match_score"] = round(max(0.0, min(score, 100.0)), 2)
        scored.append(item)

    scored.sort(key=lambda p: p["match_score"], reverse=True)
    return scored


def format_property_details(prop: Dict[str, Any]) -> str:
    """Full human-readable card for one property."""
    flags = []
    for label, key in (
        ("Parking", "parking"),
        ("Furnished", "furnished"),
        ("Balcony", "balcony"),
        ("Garden / yard", "garden"),
        ("Pool", "pool"),
        ("Elevator", "elevator"),
        ("Pet-friendly", "pet_friendly"),
        ("Near metro", "near_metro"),
    ):
        if prop.get(key):
            flags.append(label)

    lines = [
        f"**{prop.get('property_type', 'Property')} — {prop.get('property_id')}**",
        f"📍 {prop.get('neighborhood', '')}, {prop.get('city', '')}",
        f"💰 ${prop.get('price', 0):,}"
        + (f"  ·  Match {prop['match_score']}%" if "match_score" in prop else ""),
        f"🛏 {prop.get('bedrooms', '?')} bed  ·  🛁 {prop.get('bathrooms', '?')} bath  ·  "
        f"{prop.get('area_sqft', '?')} sqft",
    ]
    if prop.get("year_built"):
        lines.append(f"🏗 Built {prop['year_built']}" + (f"  ·  Condition: {prop['property_condition']}" if prop.get("property_condition") else ""))
    elif prop.get("property_condition"):
        lines.append(f"Condition: {prop['property_condition']}")
    if flags:
        lines.append("✨ " + " · ".join(flags))
    if prop.get("description"):
        lines.append(f"📝 {prop['description']}")
    return "\n".join(lines)


def format_comparison(properties: List[Dict[str, Any]]) -> str:
    """Side-by-side style comparison table as plain text."""
    if not properties:
        return "Nothing to compare."
    if len(properties) == 1:
        return format_property_details(properties[0])

    headers = ["Feature"] + [p.get("property_id", f"#{i+1}") for i, p in enumerate(properties)]
    rows = [
        ("Type", [p.get("property_type", "—") for p in properties]),
        ("Neighborhood", [f"{p.get('neighborhood', '')}, {p.get('city', '')}" for p in properties]),
        ("Price", [f"${p.get('price', 0):,}" for p in properties]),
        ("Beds / Baths", [f"{p.get('bedrooms', '?')}/{p.get('bathrooms', '?')}" for p in properties]),
        ("Area (sqft)", [str(p.get("area_sqft", "—")) for p in properties]),
        ("Year built", [str(p.get("year_built") or "—") for p in properties]),
        ("Condition", [p.get("property_condition") or "—" for p in properties]),
        ("Parking", ["Yes" if p.get("parking") else "No" for p in properties]),
        ("Pet-friendly", ["Yes" if p.get("pet_friendly") else "No" for p in properties]),
        ("Garden", ["Yes" if p.get("garden") else "No" for p in properties]),
        ("Near metro", ["Yes" if p.get("near_metro") else "No" for p in properties]),
        ("Balcony", ["Yes" if p.get("balcony") else "No" for p in properties]),
        ("Pool", ["Yes" if p.get("pool") else "No" for p in properties]),
        ("Elevator", ["Yes" if p.get("elevator") else "No" for p in properties]),
        ("Match %", [str(p.get("match_score", "—")) for p in properties]),
    ]

    # Column widths
    col_w = [max(len(headers[0]), max(len(r[0]) for r in rows))]
    for i in range(len(properties)):
        w = len(headers[i + 1])
        for r in rows:
            w = max(w, len(r[1][i]))
        col_w.append(min(w, 28))

    def pad(s: str, w: int) -> str:
        return s[:w].ljust(w)

    lines = [" | ".join(pad(headers[i], col_w[i]) for i in range(len(headers)))]
    lines.append("-+-".join("-" * col_w[i] for i in range(len(headers))))
    for label, vals in rows:
        cells = [pad(label, col_w[0])] + [pad(vals[i], col_w[i + 1]) for i in range(len(properties))]
        lines.append(" | ".join(cells))

    # Short descriptions under the table
    lines.append("")
    for p in properties:
        if p.get("description"):
            lines.append(f"{p.get('property_id')}: {p['description'][:160]}{'…' if len(p.get('description') or '') > 160 else ''}")

    return "\n".join(lines)
