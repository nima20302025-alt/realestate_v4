# -*- coding: utf-8 -*-
"""
Web app for the real-estate agent (FastAPI + LuxeHome frontend in ./static).

Run:
    uvicorn webapp:app --host 0.0.0.0 --port 7860
"""
from __future__ import annotations

import logging
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import auth_service
import config
import notify
import repositories as repo
import security
from conversation_service import chat_with_trace
from database import init_db
from matching import score_properties
from webutils import (
    SLOT_TIMES,
    build_ics,
    compare_winners,
    parse_slot,
    pct_vs,
    shape_appointment,
    to_card,
)

config.configure_logging()
log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
SORTS = {"match", "price_asc", "price_desc", "area_desc", "newest"}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Schema init at startup; never block boot so /api/health stays reachable.
    try:
        init_db()
    except Exception as exc:
        log.exception("init_db failed on startup: %s", exc)
    yield


app = FastAPI(title="LuxeHome · AI Realtor", version="2.1", lifespan=lifespan)

COOKIE_NAME = "lh_session"
SHOW_ERRORS = os.environ.get("SHOW_ERRORS", "1") != "0"

SECRET = config.SESSION_SECRET
if len(SECRET) < 24:
    SECRET = secrets.token_urlsafe(48)
    log.warning(
        "SESSION_SECRET is not set (or too short): using a random one. Everyone is signed out on every "
        "restart. Set SESSION_SECRET in Railway Variables."
    )
LIMITER = security.RateLimiter()

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── security plumbing ───────────────────────────────────────────────────────


def client_ip(request: Request) -> str:
    # Railway's edge sets X-Real-IP; otherwise fall back to the socket / uvicorn-resolved address.
    real = (request.headers.get("x-real-ip") or "").strip()
    if real:
        return real[:64]
    return request.client.host if request.client else "unknown"


def _limit(key: str, limit: int, window: int, message: str) -> None:
    ok, retry = LIMITER.check(key, limit, window)
    if not ok:
        raise HTTPException(429, message, headers={"Retry-After": str(retry)})


def _is_https(request: Request) -> bool:
    if config.COOKIE_SECURE == "1":
        return True
    proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "").split(",")[0].strip()
    return proto == "https"


def _set_session_cookie(request: Request, response: Response, customer_id: int) -> None:
    token = security.make_session_token(customer_id, SECRET, days=config.SESSION_DAYS)
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=config.SESSION_DAYS * 86400,
        httponly=True,
        secure=_is_https(request),
        samesite="lax",
        path="/",
    )


def optional_customer(request: Request) -> Optional[int]:
    return security.read_session_token(request.cookies.get(COOKIE_NAME), SECRET)


def current_customer(request: Request) -> int:
    cid = optional_customer(request)
    if cid is None:
        raise HTTPException(401, "Your session expired. Refresh the page to continue.")
    return cid


def _origin_ok(origin: str, request: Request) -> bool:
    host = urlparse(origin).netloc.lower()
    allowed = {
        (request.headers.get("host") or "").lower(),
        (request.headers.get("x-forwarded-host") or "").split(",")[0].strip().lower(),
        *config.ALLOWED_ORIGINS,
    }
    return bool(host) and host in allowed


@app.middleware("http")
async def guard(request: Request, call_next):
    """Block cross-site writes, add basic security headers, keep API responses uncached."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        origin = request.headers.get("origin")
        if origin and not _origin_ok(origin, request):
            return JSONResponse(status_code=403, content={"detail": "Cross-site request blocked."})
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


# ── error handling ──────────────────────────────────────────────────────────


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    log.exception("Unhandled error on %s", request.url.path)
    detail = f"{type(exc).__name__}: {str(exc)[:300]}" if SHOW_ERRORS else "Something went wrong on our side."
    return JSONResponse(status_code=500, content={"detail": detail})


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, exc: RequestValidationError):
    errors = exc.errors()
    first = errors[0] if errors else {}
    loc = ".".join(str(x) for x in first.get("loc", ()) if x not in ("body", "query"))
    return JSONResponse(
        status_code=422,
        content={"detail": f"Invalid {loc or 'input'}: {first.get('msg', 'bad value')}"},
    )


# ── request models ──────────────────────────────────────────────────────────


class ProfileIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)


class AuthStartIn(BaseModel):
    contact: str = Field(..., min_length=3, max_length=254)


class AuthVerifyIn(BaseModel):
    contact: str = Field(..., min_length=3, max_length=254)
    code: str = Field(..., min_length=4, max_length=12)


class SearchIn(BaseModel):
    city: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    budget_max: Optional[int] = None
    budget_min: Optional[int] = None
    min_area: Optional[int] = None
    property_type: Optional[str] = None
    listing_type: str = "Sale"
    parking: Optional[bool] = None
    garden: Optional[bool] = None
    near_metro: Optional[bool] = None
    pet_friendly: Optional[bool] = None
    sort: str = "match"
    limit: int = 12


class ChatIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


class BookIn(BaseModel):
    property_id: str
    appointment_date: str
    appointment_time: str = "10:00"
    notes: Optional[str] = Field(None, max_length=500)


class RescheduleIn(BaseModel):
    appointment_date: str
    appointment_time: str


# ── health / meta ───────────────────────────────────────────────────────────


@app.get("/api/health")
def health():
    return {"ok": True, "provider": config.LLM_PROVIDER}


@app.get("/api/diag")
def diag(token: str = ""):
    """Safe diagnostics (no secrets). Set DIAG_TOKEN to require ?token=... (recommended)."""
    full = True
    if config.DIAG_TOKEN:
        if not secrets.compare_digest(token.encode(), config.DIAG_TOKEN.encode()):
            raise HTTPException(404, "Not found")
    else:
        full = False  # no token configured: only coarse yes/no information
    info: Dict[str, Any] = {
        "provider": config.LLM_PROVIDER,
        "groq_key_set": bool(config.GROQ_API_KEY),
        "google_key_set": bool(config.GOOGLE_API_KEY),
        "database_url_set": bool(config.DATABASE_URL),
        "session_secret_set": len(config.SESSION_SECRET) >= 24,
        "email_login": notify.is_configured("email"),
        "sms_login": notify.is_configured("phone"),
        "auth_dev_mode": config.AUTH_DEV_MODE,
    }
    if full:
        info["model"] = config.GROQ_MODEL if config.LLM_PROVIDER == "groq" else config.GEMINI_MODEL
    try:
        from database import get_connection

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM properties")
                info["db_ok"] = True
                info["properties"] = cur.fetchone()[0]
    except Exception as exc:
        info["db_ok"] = False
        if full:
            info["db_error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
    return info


@app.get("/favicon.ico")
def favicon():
    import base64

    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    return Response(content=png, media_type="image/png")


@app.get("/api/meta")
def meta():
    return repo.get_market_meta()


# ── session / account ──────────────────────────────────────────────────────


def _me(cid: int) -> Dict[str, Any]:
    c = repo.get_customer(cid)
    if not c:
        raise HTTPException(401, "Your session expired. Refresh the page to continue.")
    contact, channel = None, None
    if c.get("phone_verified") and c.get("phone"):
        channel, contact = "phone", security.mask_contact("phone", c["phone"])
    elif c.get("email_verified") and c.get("email"):
        channel, contact = "email", security.mask_contact("email", c["email"])
    return {"customer_id": c["customer_id"], "name": c["name"], "verified": bool(contact), "contact": contact, "channel": channel}


@app.post("/api/session")
def create_session(request: Request, response: Response):
    """Resume the signed-in browser session, or start a new anonymous (guest) one."""
    cid = optional_customer(request)
    if cid and repo.get_customer(cid):
        _set_session_cookie(request, response, cid)  # sliding expiry
        return _me(cid)
    _limit(f"session:{client_ip(request)}", config.SESSION_CREATE_PER_HOUR_IP, 3600,
           "Too many new sessions from your network. Try again later.")
    cid = repo.create_customer(name="Guest")
    _set_session_cookie(request, response, cid)
    return _me(cid)


@app.get("/api/me")
def me(request: Request):
    return _me(current_customer(request))


@app.patch("/api/me")
def update_me(body: ProfileIn, request: Request):
    cid = current_customer(request)
    name = " ".join(body.name.split())[:60]
    if not name:
        raise HTTPException(400, "Enter a name.")
    repo.update_customer(cid, name=name)
    return _me(cid)


@app.post("/api/auth/start")
def auth_start(body: AuthStartIn, request: Request):
    current_customer(request)
    ip = client_ip(request)
    _limit(f"auth:{ip}", config.AUTH_IP_PER_HOUR, 3600, "Too many sign-in attempts. Try again later.")
    try:
        return auth_service.start_login(
            repo, body.contact, SECRET,
            is_configured=notify.is_configured, send=notify.send_code,
            dev_mode=config.AUTH_DEV_MODE, daily_cap=config.AUTH_CODES_PER_DAY,
        )
    except auth_service.AuthError as exc:
        raise HTTPException(exc.status, exc.message)


@app.post("/api/auth/verify")
def auth_verify(body: AuthVerifyIn, request: Request, response: Response):
    cid = current_customer(request)
    _limit(f"verify:{client_ip(request)}", config.AUTH_IP_PER_HOUR * 3, 3600, "Too many attempts. Try again later.")
    try:
        result = auth_service.verify_login(repo, body.contact, body.code, cid, SECRET)
    except auth_service.AuthError as exc:
        raise HTTPException(exc.status, exc.message)
    _set_session_cookie(request, response, result["customer_id"])
    return {**_me(result["customer_id"]), "switched": result["switched"], "merged": result["merged"]}


@app.post("/api/auth/logout")
def auth_logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@app.get("/api/history")
def history(request: Request, limit: int = Query(40, ge=1, le=200)):
    cid = current_customer(request)
    return {"messages": repo.load_history(cid)[-limit:]}


# ── search / property / compare ─────────────────────────────────────────────


@app.post("/api/search")
def search(body: SearchIn, request: Request):
    req: Dict[str, Any] = {"listing_type": body.listing_type or "Sale"}
    for key in ("city", "property_type"):
        val = getattr(body, key)
        if val:
            req[key] = val.strip()
    for key in ("bedrooms", "bathrooms"):
        val = getattr(body, key)
        if val:
            req[key] = val
    if body.budget_max:
        req["budget_absolute_max"] = body.budget_max
    if body.budget_min:
        req["budget_minimum"] = body.budget_min
    if body.min_area:
        req["min_area_sqft"] = body.min_area
    for flag in ("parking", "garden", "near_metro", "pet_friendly"):
        if getattr(body, flag):
            req[flag] = True

    sort = body.sort if body.sort in SORTS else "match"
    limit = max(1, min(body.limit, 60))
    total = repo.count_properties(req)

    if sort == "match":
        scoring = dict(req)
        if body.budget_max:
            scoring["budget_preferred"] = body.budget_max
        pool = repo.search_properties(req, limit=max(config.SEARCH_RESULT_LIMIT, 400))
        ranked = score_properties(pool, scoring, customer_id=optional_customer(request))[:limit]
        cards = [to_card(p) for p in ranked]
    else:
        rows = repo.search_properties(req, limit=limit, order_by=sort)
        cards = [to_card(p) for p in rows]

    return {"count": total, "showing": len(cards), "properties": cards}


@app.get("/api/property/{property_id}")
def property_detail(property_id: str):
    prop = repo.get_property(property_id.strip().upper())
    if not prop:
        raise HTTPException(404, "Property not found")
    card = to_card(prop, desc_len=None)

    stats = repo.get_city_stats(prop["city"]) or {}
    avg_price, avg_ppsf = stats.get("avg_price"), stats.get("avg_ppsf")
    card["insights"] = {
        "city": prop["city"],
        "listings_in_city": stats.get("n"),
        "avg_price": round(avg_price) if avg_price else None,
        "avg_price_per_sqft": round(avg_ppsf) if avg_ppsf else None,
        "avg_area_sqft": round(stats["avg_area"]) if stats.get("avg_area") else None,
        "price_vs_city_pct": pct_vs(card["price"], avg_price),
        "ppsf_vs_city_pct": pct_vs(card["price_per_sqft"], avg_ppsf),
    }
    card["similar"] = [to_card(p) for p in repo.find_similar(prop, 4)]
    return card


@app.get("/api/compare")
def compare(ids: str = Query(..., description="comma separated property ids (2-4)")):
    id_list: List[str] = []
    for raw in ids.split(","):
        pid = raw.strip().upper()
        if pid and pid not in id_list:
            id_list.append(pid)
    id_list = id_list[:4]
    if len(id_list) < 2:
        raise HTTPException(400, "Pick at least two different properties to compare.")
    props = repo.get_properties_by_ids(id_list)
    if len(props) < 2:
        raise HTTPException(404, "Could not load enough of those properties.")

    stats_by_city: Dict[str, Dict[str, Any]] = {}
    cards = []
    for p in props:
        card = to_card(p, desc_len=None)
        key = (p.get("city") or "").lower()
        if key not in stats_by_city:
            stats_by_city[key] = repo.get_city_stats(p["city"]) or {}
        st = stats_by_city[key]
        card["city_avg_price"] = round(st["avg_price"]) if st.get("avg_price") else None
        card["city_avg_ppsf"] = round(st["avg_ppsf"]) if st.get("avg_ppsf") else None
        card["vs_city_pct"] = pct_vs(card["price"], st.get("avg_price"))
        card["ppsf_vs_city_pct"] = pct_vs(card["price_per_sqft"], st.get("avg_ppsf"))
        cards.append(card)
    return {"properties": cards, "winners": compare_winners(cards)}


# ── favorites ───────────────────────────────────────────────────────────────


@app.get("/api/favorites")
def favorites(request: Request):
    cid = current_customer(request)
    ids = repo.list_favorite_ids(cid)
    props = repo.get_properties_by_ids(ids) if ids else []
    return {"ids": [p["property_id"] for p in props], "properties": [to_card(p) for p in props]}


@app.post("/api/favorites/{property_id}")
def add_favorite(property_id: str, request: Request):
    cid = current_customer(request)
    pid = property_id.strip().upper()
    if not repo.get_property(pid):
        raise HTTPException(404, "Property not found")
    repo.add_favorite(cid, pid)
    try:
        repo.save_property_interaction(cid, pid, "like", reason="added to favorites")
    except Exception:
        log.exception("favorite interaction not saved")
    return {"ok": True, "property_id": pid}


@app.delete("/api/favorites/{property_id}")
def remove_favorite(property_id: str, request: Request):
    repo.remove_favorite(current_customer(request), property_id.strip().upper())
    return {"ok": True}


# ── appointments ────────────────────────────────────────────────────────────


@app.get("/api/slots")
def slots(property_id: str, date: str):
    try:
        parse_slot(date, SLOT_TIMES[0])
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    free = set(repo.get_available_slots(property_id.strip().upper(), date))
    return {"date": date, "slots": [{"time": t, "available": t in free} for t in SLOT_TIMES]}


@app.get("/api/appointments")
def appointments(request: Request, include_history: bool = False):
    cid = current_customer(request)
    rows = repo.get_appointments_detailed(cid, include_history=include_history)
    return {"appointments": [shape_appointment(r) for r in rows]}


@app.post("/api/book")
def book_appointment(body: BookIn, request: Request):
    cid = current_customer(request)
    try:
        parse_slot(body.appointment_date, body.appointment_time)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    pid = body.property_id.strip().upper()
    if not repo.get_property(pid):
        raise HTTPException(404, "Property not found")
    _limit(f"book:{cid}", 20, 3600, "You're booking a lot of viewings. Try again in a bit.")

    notes = (body.notes or "").strip() or None
    result = repo.create_appointment(cid, pid, body.appointment_date, body.appointment_time, notes=notes)
    if not result.get("success"):
        raise HTTPException(409, result.get("message") or "Could not book")

    try:  # same taste signal the chat tool records
        repo.save_property_interaction(cid, pid, "like", reason="booked viewing")
        repo.save_taste_insight(
            cid,
            insight="booked a viewing - strong positive signal",
            source_property_id=pid,
            source_action="like",
            reason="booked viewing",
            weight=1.5,
        )
    except Exception:
        log.exception("booking taste signal not saved")

    detail = repo.get_appointment_detailed(result["appointment_id"], cid)
    return {**result, "appointment": shape_appointment(detail) if detail else None}


@app.post("/api/appointments/{appointment_id}/reschedule")
def reschedule(appointment_id: int, body: RescheduleIn, request: Request):
    cid = current_customer(request)
    try:
        parse_slot(body.appointment_date, body.appointment_time)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    result = repo.reschedule_appointment(appointment_id, cid, body.appointment_date, body.appointment_time)
    if not result.get("success"):
        raise HTTPException(409, result.get("message") or "Could not reschedule")
    detail = repo.get_appointment_detailed(appointment_id, cid)
    return {**result, "appointment": shape_appointment(detail) if detail else None}


@app.post("/api/appointments/{appointment_id}/cancel")
def cancel_appointment(appointment_id: int, request: Request):
    if not repo.cancel_appointment(appointment_id, current_customer(request)):
        raise HTTPException(404, "Appointment not found or already cancelled")
    return {"ok": True}


@app.get("/api/appointments/{appointment_id}/ics")
def appointment_ics(appointment_id: int, request: Request):
    row = repo.get_appointment_detailed(appointment_id, current_customer(request))
    if not row:
        raise HTTPException(404, "Appointment not found")
    ics = build_ics(shape_appointment(row))
    return Response(
        content=ics,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="viewing-{appointment_id}.ics"'},
    )


# ── chat ────────────────────────────────────────────────────────────────────


def _property_ids_from_trace(trace) -> (List[str], Dict[str, float], List[str]):
    """Cards to show under the reply, taken from what the tools really returned."""
    ids: List[str] = []
    scores: Dict[str, float] = {}
    compare_ids: List[str] = []
    for t in trace or []:
        data = t.data if isinstance(t.data, dict) else None
        if not t.ok or not data:
            continue
        if t.name in ("search_properties", "compare_properties"):
            found = [p for p in data.get("properties", []) if isinstance(p, dict) and p.get("property_id")]
            for p in found:
                ids.append(p["property_id"])
                if p.get("match_score") is not None:
                    scores[p["property_id"]] = p["match_score"]
            if t.name == "compare_properties":
                compare_ids = [p["property_id"] for p in found]
        elif t.name == "get_property_details":
            pid = (data.get("property") or {}).get("property_id")
            if pid:
                ids.append(pid)
        elif t.name == "list_favorites":
            ids += [p["property_id"] for p in data.get("favorites", []) if isinstance(p, dict) and p.get("property_id")]
    seen, ordered = set(), []
    for pid in ids:
        if pid not in seen:
            seen.add(pid)
            ordered.append(pid)
    return ordered[:8], scores, compare_ids


@app.post("/api/chat")
def chat_api(body: ChatIn, request: Request):
    cid = current_customer(request)
    ip = client_ip(request)
    _limit("chat:global", config.CHAT_GLOBAL_PER_DAY, 86400, "The assistant has reached today's usage limit. Please try again tomorrow.")
    _limit(f"chat:min:{cid}", config.CHAT_PER_MIN, 60, "You're sending messages too fast. Give it a few seconds.")
    _limit(f"chat:ip:{ip}", config.CHAT_IP_PER_MIN, 60, "Too many messages from your network. Give it a few seconds.")
    _limit(f"chat:day:{cid}", config.CHAT_PER_DAY, 86400, "You've reached today's message limit. Please come back tomorrow.")
    reply, trace = chat_with_trace(cid, body.message.strip())
    tools = [
        {
            "name": t.name,
            "ok": t.ok,
            "summary": t.summary,
            "args": {k: v for k, v in (t.args or {}).items() if v not in (None, "", False)},
        }
        for t in (trace or [])
    ]

    props_out: List[Dict[str, Any]] = []
    compare_ids: List[str] = []
    try:
        ids, scores, compare_ids = _property_ids_from_trace(trace)
        if ids:
            rows = repo.get_properties_by_ids(ids)
            props_out = [to_card(p, match_score=scores.get(p["property_id"])) for p in rows]
    except Exception:
        log.exception("could not build property cards for chat reply")

    return {"reply": reply, "tools": tools, "properties": props_out, "compare_ids": compare_ids}


# ── frontend ────────────────────────────────────────────────────────────────


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})


def main():
    import uvicorn

    port = int(os.environ.get("PORT", "7860"))
    uvicorn.run(
        "webapp:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
