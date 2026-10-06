# -*- coding: utf-8 -*-
"""
LangChain tools the agent can call. Each tool closes over customer_id
via a factory so the LLM never invents an ID.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

import config
import repositories as repo
from matching import format_comparison, format_property_details, score_properties

logger = logging.getLogger(__name__)


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def build_tools(customer_id: int):
    """Return tool list bound to this customer."""

    @tool
    def search_properties(
        listing_type: Optional[str] = None,
        city: Optional[str] = None,
        neighborhood: Optional[str] = None,
        property_type: Optional[str] = None,
        bedrooms: Optional[int] = None,
        bathrooms: Optional[int] = None,
        budget_preferred: Optional[int] = None,
        budget_minimum: Optional[int] = None,
        budget_absolute_max: Optional[int] = None,
        min_area_sqft: Optional[int] = None,
        parking: Optional[bool] = None,
        furnished: Optional[bool] = None,
        balcony: Optional[bool] = None,
        garden: Optional[bool] = None,
        pool: Optional[bool] = None,
        elevator: Optional[bool] = None,
        pet_friendly: Optional[bool] = None,
        near_metro: Optional[bool] = None,
        limit: int = 5,
    ) -> str:
        """Search listings in the USA Housing inventory (King County / greater Seattle).
        listing_type is almost always Sale in this dataset. city examples: Seattle, Bellevue,
        Redmond, Kirkland, Renton, Issaquah, Sammamish, Kent, Auburn.
        Budget fields are USD integers (e.g. 600000). Boolean flags filter to true only.
        Returns a ranked shortlist with match scores and property IDs like USA00042."""
        requirements: Dict[str, Any] = {}
        # Default to Sale — this dataset has no rentals
        if not listing_type:
            listing_type = "Sale"
        for k, v in {
            "listing_type": listing_type,
            "city": city,
            "neighborhood": neighborhood,
            "property_type": property_type,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "budget_preferred": budget_preferred,
            "budget_minimum": budget_minimum,
            "budget_absolute_max": budget_absolute_max,
            "min_area_sqft": min_area_sqft,
            "parking": parking,
            "furnished": furnished,
            "balcony": balcony,
            "garden": garden,
            "pool": pool,
            "elevator": elevator,
            "pet_friendly": pet_friendly,
            "near_metro": near_metro,
        }.items():
            if v is not None and v != "":
                requirements[k] = v

        # Persist soft preferences for memory
        for k, v in requirements.items():
            try:
                repo.save_preference(customer_id, k, v)
            except Exception:
                logger.exception("save_preference failed")

        candidates = repo.search_properties(requirements, limit=config.SEARCH_RESULT_LIMIT)
        ranked = score_properties(candidates, requirements, customer_id=customer_id)
        top = ranked[: max(1, min(limit, config.RECOMMEND_TOP_N * 2))]

        if not top:
            return _json({"count": 0, "properties": [], "message": "No matches. Suggest relaxing budget, city, or bedrooms."})

        slim = []
        for i, p in enumerate(top, 1):
            slim.append(
                {
                    "n": i,
                    "property_id": p["property_id"],
                    "property_type": p.get("property_type"),
                    "city": p.get("city"),
                    "neighborhood": p.get("neighborhood"),
                    "price": p.get("price"),
                    "bedrooms": p.get("bedrooms"),
                    "bathrooms": p.get("bathrooms"),
                    "area_sqft": p.get("area_sqft"),
                    "parking": bool(p.get("parking")),
                    "pet_friendly": bool(p.get("pet_friendly")),
                    "garden": bool(p.get("garden")),
                    "near_metro": bool(p.get("near_metro")),
                    "match_score": p.get("match_score"),
                }
            )
        return _json({"count": len(ranked), "showing": len(slim), "properties": slim})

    @tool
    def get_property_details(property_id: str) -> str:
        """Full details for one listing by property_id (e.g. USA00042)."""
        prop = repo.get_property(property_id.strip().upper())
        if not prop:
            return _json({"error": f"Property {property_id} not found"})
        return _json({"property": prop, "card": format_property_details(prop)})

    @tool
    def compare_properties(property_ids: List[str]) -> str:
        """Side-by-side comparison of 2–4 properties by ID list, e.g. [\"USA00001\", \"USA00003\"]."""
        ids = [p.strip().upper() for p in property_ids if p]
        if len(ids) < 2:
            return _json({"error": "Need at least two property IDs to compare"})
        props = repo.get_properties_by_ids(ids[:4])
        if len(props) < 2:
            return _json({"error": "Could not load enough properties", "found": [p.get("property_id") for p in props]})
        profile = repo.get_customer_profile(customer_id)
        req = {k: _coerce(v) for k, v in profile.items()}
        props = score_properties(props, req, customer_id=customer_id)
        return _json({"properties": props, "table": format_comparison(props)})

    @tool
    def save_feedback(property_id: str, action: str, reason: Optional[str] = None) -> str:
        """Record like/reject/interested/not_interested on a property, with optional reason.
        action: like | reject | interested | not_interested.
        Use this whenever the customer praises, criticizes, or dismisses a listing — reason is gold for taste memory."""
        action = (action or "").strip().lower()
        if action not in ("like", "reject", "interested", "not_interested"):
            return _json({"error": "action must be like, reject, interested, or not_interested"})
        pid = property_id.strip().upper()
        prop = repo.get_property(pid)
        if not prop:
            return _json({"error": f"Property {pid} not found"})

        repo.save_property_interaction(customer_id, pid, action, reason=reason)

        insight = None
        if reason:
            insight = reason.strip()[:200]
            weight = 1.5 if action in ("reject", "not_interested") else 1.0
            repo.save_taste_insight(
                customer_id,
                insight=insight,
                source_property_id=pid,
                source_action=action,
                reason=reason,
                weight=weight,
            )
        elif action in ("like", "interested"):
            repo.save_taste_insight(
                customer_id,
                insight=f"liked {prop.get('property_type')} in {prop.get('neighborhood')}",
                source_property_id=pid,
                source_action=action,
                weight=1.0,
            )

        return _json({"ok": True, "property_id": pid, "action": action, "reason": reason, "insight_saved": bool(insight or action)})

    @tool
    def get_customer_memory() -> str:
        """Load known preferences and taste insights for this customer. Call at the start of complex requests."""
        profile = repo.get_customer_profile(customer_id)
        taste = repo.get_taste_summary(customer_id)
        interactions = repo.get_customer_interactions(customer_id)[:10]
        return _json({"preferences": profile, "taste_summary": taste, "recent_interactions": interactions})

    @tool
    def get_available_slots(property_id: str, appointment_date: str) -> str:
        """List open viewing slots for a property on a date (YYYY-MM-DD). Hours 09:00–17:00."""
        pid = property_id.strip().upper()
        slots = repo.get_available_slots(pid, appointment_date)
        return _json({"property_id": pid, "date": appointment_date, "slots": slots})

    @tool
    def book_appointment(property_id: str, appointment_date: str, appointment_time: str) -> str:
        """Book a viewing. date YYYY-MM-DD, time HH:MM (24h). Check get_available_slots first when unsure."""
        pid = property_id.strip().upper()
        result = repo.create_appointment(customer_id, pid, appointment_date, appointment_time)
        if result.get("success"):
            repo.save_property_interaction(customer_id, pid, "like", reason="booked viewing")
            repo.save_taste_insight(
                customer_id,
                insight="booked a viewing — strong positive signal",
                source_property_id=pid,
                source_action="like",
                reason="booked viewing",
                weight=1.5,
            )
        return _json(result)

    @tool
    def list_appointments() -> str:
        """Show this customer's scheduled viewings."""
        appts = [a for a in repo.get_customer_appointments(customer_id) if a.get("status") == "scheduled"]
        return _json({"appointments": appts})

    @tool
    def cancel_appointment(appointment_id: int) -> str:
        """Cancel a scheduled appointment by its numeric ID."""
        ok = repo.cancel_appointment(int(appointment_id), customer_id)
        return _json({"ok": ok, "appointment_id": appointment_id})

    @tool
    def add_favorite(property_id: str) -> str:
        """Save a property to the customer's favorites / shortlist."""
        pid = property_id.strip().upper()
        if not repo.get_property(pid):
            return _json({"error": f"Property {pid} not found"})
        repo.add_favorite(customer_id, pid)
        repo.save_property_interaction(customer_id, pid, "like", reason="added to favorites")
        return _json({"ok": True, "property_id": pid})

    @tool
    def list_favorites() -> str:
        """List property IDs the customer favorited."""
        profile = repo.get_customer_profile(customer_id)
        ids = [k.split(":", 1)[1] for k in profile if k.startswith("favorite:")]
        props = repo.get_properties_by_ids(ids) if ids else []
        slim = [
            {
                "property_id": p["property_id"],
                "city": p.get("city"),
                "neighborhood": p.get("neighborhood"),
                "price": p.get("price"),
                "bedrooms": p.get("bedrooms"),
                "property_type": p.get("property_type"),
            }
            for p in props
        ]
        return _json({"favorites": slim})

    return [
        search_properties,
        get_property_details,
        compare_properties,
        save_feedback,
        get_customer_memory,
        get_available_slots,
        book_appointment,
        list_appointments,
        cancel_appointment,
        add_favorite,
        list_favorites,
    ]


def _coerce(v: str):
    if v is None:
        return None
    low = str(v).lower()
    if low in ("true", "1", "yes"):
        return True
    if low in ("false", "0", "no"):
        return False
    try:
        if "." not in str(v):
            return int(v)
    except ValueError:
        pass
    return v
