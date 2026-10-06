# -*- coding: utf-8 -*-
"""
Central configuration for the real-estate agent (Supabase / Postgres).

Set DATABASE_URL to your Supabase Postgres connection string, e.g.:
  postgresql://postgres.[ref]:[PASSWORD]@aws-0-[region].pooler.supabase.com:6543/postgres
or the direct one:
  postgresql://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres

Never commit a real .env file.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# Supabase / Postgres connection string (required for DB operations)
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Optional: Supabase project URL + service role key (if you prefer supabase-py later)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

# LLM
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "groq").lower()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

# --- security / sign-in ---------------------------------------------------
# Long random string used to sign session cookies and hash login codes.
# Generate one:  python -c "import secrets; print(secrets.token_urlsafe(48))"
SESSION_SECRET = os.environ.get("SESSION_SECRET", "")
SESSION_DAYS = int(os.environ.get("SESSION_DAYS", "90"))
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "")  # "1" forces the Secure flag
ALLOWED_ORIGINS = [h.strip().lower() for h in os.environ.get("ALLOWED_ORIGINS", "").split(",") if h.strip()]
DIAG_TOKEN = os.environ.get("DIAG_TOKEN", "")
ENABLE_RLS = os.environ.get("ENABLE_RLS", "1") != "0"

# Verification codes (email via Resend, SMS via Twilio). With neither configured,
# sign-in is unavailable unless AUTH_DEV_MODE=1 (code is logged + returned: NEVER in production).
AUTH_DEV_MODE = os.environ.get("AUTH_DEV_MODE", "0") == "1"
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
MAIL_FROM = os.environ.get("MAIL_FROM", "")  # e.g. "LuxeHome <login@yourdomain.com>"
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM = os.environ.get("TWILIO_FROM", "")
TWILIO_MESSAGING_SERVICE_SID = os.environ.get("TWILIO_MESSAGING_SERVICE_SID", "")

# Rate limits (in-memory, per server process)
CHAT_PER_MIN = int(os.environ.get("CHAT_PER_MIN", "8"))
CHAT_PER_DAY = int(os.environ.get("CHAT_PER_DAY", "150"))
CHAT_IP_PER_MIN = int(os.environ.get("CHAT_IP_PER_MIN", "20"))
CHAT_GLOBAL_PER_DAY = int(os.environ.get("CHAT_GLOBAL_PER_DAY", "5000"))  # cost circuit-breaker
AUTH_IP_PER_HOUR = int(os.environ.get("AUTH_IP_PER_HOUR", "20"))
AUTH_CODES_PER_DAY = int(os.environ.get("AUTH_CODES_PER_DAY", "6"))
SESSION_CREATE_PER_HOUR_IP = int(os.environ.get("SESSION_CREATE_PER_HOUR_IP", "30"))

SEARCH_RESULT_LIMIT = int(os.environ.get("SEARCH_RESULT_LIMIT", "100"))
RECOMMEND_TOP_N = int(os.environ.get("RECOMMEND_TOP_N", "5"))
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")


def configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )


def require_database_url() -> str:
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not set.\n"
            "In Supabase: Project Settings → Database → Connection string (URI).\n"
            "In Colab: add Secret named DATABASE_URL, then re-run the secrets cell.\n"
            "Example: postgresql://postgres.[ref]:[PASSWORD]@aws-0-xx.pooler.supabase.com:6543/postgres"
        )
    url = DATABASE_URL.strip().strip('"').strip("'")
    # Supabase usually needs SSL; add if missing
    if "sslmode=" not in url.lower():
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}sslmode=require"
    return url
