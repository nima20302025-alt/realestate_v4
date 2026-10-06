# LuxeHome · AI Real Estate Agent (Railway)

FastAPI web app + LangGraph tool-calling agent + Supabase Postgres.

## Deploy on Railway

### 1. Create project
1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**  
   (or **Empty Project** and upload / connect this folder).
2. Root directory = this folder (contains `webapp.py`).

### 2. Variables (Settings → Variables)
| Name | Required | Example |
|------|----------|---------|
| `DATABASE_URL` | yes | Supabase **pooler** URI (port `6543` recommended from Railway) |
| `GROQ_API_KEY` | yes | from https://console.groq.com/keys |
| `LLM_PROVIDER` | no | `groq` (default) |
| `GROQ_MODEL` | no | e.g. `llama-3.3-70b-versatile` or your preferred Groq model |
| `LOG_LEVEL` | no | `INFO` |

Railway sets `PORT` automatically — do not hardcode it.

### 3. Start command
Already in `Procfile` / `railway.toml`:

```bash
uvicorn webapp:app --host 0.0.0.0 --port $PORT
```

### 4. Public URL
After deploy: **Settings → Networking → Generate Domain**.

Open `https://YOUR-APP.up.railway.app` — LuxeHome UI loads at `/`.

### 5. Database
- Schema is created automatically on startup (`init_db`).
- Import listings once (from your machine or a one-off Railway shell):

```bash
pip install -r requirements-import.txt
python import_usa_housing.py --csv USA_Housing_Dataset.csv --reset
```

Upload the CSV to the service or run import from Colab against the same `DATABASE_URL`.

### 6. Supabase network
Allow Railway egress (Supabase → Database → usually open, or allow all IPs for pooler). Prefer **connection pooler** URI from external hosts.

## Local run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill secrets
uvicorn webapp:app --host 0.0.0.0 --port 7860
```

## API smoke test

```bash
curl https://YOUR-APP.up.railway.app/api/health   # server is up
curl https://YOUR-APP.up.railway.app/api/diag     # keys set? DB reachable? (no secrets shown)
```

Set `SHOW_ERRORS=0` in Railway Variables once everything works to hide `[debug]` error details from chat replies.

## Project layout

```
webapp.py              # FastAPI + LuxeHome UI
agent.py               # LangGraph agent
tools.py               # search / book / favorites tools
conversation_service.py
repositories.py / database.py / matching.py
config.py / llm_service.py
import_usa_housing.py  # one-time CSV import
requirements.txt
Procfile
railway.toml
```

## Notes
- Do not commit `.env`.
- Free Railway tier sleeps after idle; first request may be slow.
- If chat fails, check Railway **Deploy Logs** for Groq/DB errors.

## Build notes (Railway)

- No ngrok / tunnel needed: Railway gives the public URL and the UI calls the API with relative paths.
- Do **not** use a custom `nixpacks.toml` unless you know the full Python setup.
- Railway detects Python from `requirements.txt` + `.python-version`.
- If build fails with `pip: command not found`, remove any custom install commands in the Railway UI (Settings → Build → Custom Build Command should be empty).

## What the UI can do (v2)

- **Chat** with property cards built from what the tools really returned (Compare / Book / Save on every card), friendly tool chips, chat history that survives a page refresh, Persian/English text direction.
- **Explore**: filters (city, type, beds, baths, price like `400k` / `1.2m`, size, amenities that exist in your data), sorting, "show more".
- **Home details**: market snapshot vs the city average (price and $/sqft), similar homes, map link, and a mortgage calculator.
- **Compare** 2-4 homes side by side: best value highlighted per row, overall pick, editable down payment / rate / term for monthly cost.
- **Saved homes**, **Viewings**: book with a day + time-slot picker (taken slots greyed out), notes for the agent, reschedule, cancel, history, **Add to calendar (.ics)**.
- Light / dark theme, mobile layout with bottom navigation.

Endpoints (the signed-in user is read from the session cookie — no ids in URLs): `/api/session`, `/api/me`, `/api/auth/start|verify|logout`, `/api/history`, `/api/meta`, `/api/property/{id}`, `/api/compare?ids=A,B`, `/api/favorites`, `/api/slots`, `/api/appointments` (+ `/{id}/reschedule`, `/{id}/cancel`, `/{id}/ics`), `/api/book`, `/api/chat`.
The first start adds the new columns/tables (`appointments.notes`, `customers.*_verified`, `auth_codes`) automatically.

Run the unit tests: `python -m unittest tests.test_webutils -v`

## Security (read before going public)

**Sessions.** The browser gets an `HttpOnly`, `SameSite=Lax`, `Secure` cookie signed with `SESSION_SECRET`. Every endpoint reads the customer from that cookie, never from a client-supplied id, so nobody can see or cancel someone else's viewings by guessing numbers. Cross-site writes are rejected (Origin check).

**Variables to set in Railway**

| Name | Why |
|------|-----|
| `SESSION_SECRET` | **Required.** Long random string (`python -c "import secrets; print(secrets.token_urlsafe(48))"`). Without it a random one is used and everybody is signed out on each deploy. |
| `RESEND_API_KEY` + `MAIL_FROM` | Email codes via [Resend](https://resend.com). `MAIL_FROM` must be on a domain you verified there, e.g. `LuxeHome <login@yourdomain.com>`. |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM` (or `TWILIO_MESSAGING_SERVICE_SID`) | Optional SMS codes. US numbers need Twilio A2P 10DLC registration; email is much easier to start with. |
| `DIAG_TOKEN` | Protects `/api/diag?token=...` (without it only coarse yes/no info is shown). |
| `SHOW_ERRORS=0` | Hide technical error details from users in production. |
| `AUTH_DEV_MODE` | **Never set in production.** Logs the code and returns it in the API response so you can test sign-in without an email/SMS provider. |

**Sign-in.** A visitor starts as an anonymous guest. Entering an email or phone number sends a 6-digit code (valid 10 min, 5 attempts, stored only as a keyed hash, 60 s between sends, 6 per day per contact). Confirming a contact that already has an account signs the visitor into it and merges whatever the guest had collected (saved homes, viewings, chat). Phone numbers are normalised (`206-555-0123` → `+12065550123`).

**Rate limits** (per process, in memory; tune with env vars): `CHAT_PER_MIN=8`, `CHAT_PER_DAY=150`, `CHAT_IP_PER_MIN=20`, `CHAT_GLOBAL_PER_DAY=5000` (cost circuit-breaker), `AUTH_IP_PER_HOUR=20`, `AUTH_CODES_PER_DAY=6`, `SESSION_CREATE_PER_HOUR_IP=30`. Counters reset on redeploy; if you ever run several instances, move them to Redis.

**Database.** Row Level Security is enabled on all personal-data tables at startup (set `ENABLE_RLS=0` to skip). The app connects as the table owner, which bypasses RLS, while Supabase's public REST API (anon key) can no longer read them.

Run the unit tests: `python -m unittest discover -s tests -v`
