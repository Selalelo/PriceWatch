# PriceWatch ZAR

**A production-grade AI-powered commodity price monitor built for the South African market.**

Live gold and oil prices in ZAR, with user authentication, email verification, personal portfolios, price alerts, and an AI chat assistant — all deployed on Render with automated price fetching via GitHub Actions.

---

## Architecture & Communication Flow

### Full System

```
Developer
    │
    │  git push main
    ▼
GitHub
    ├── Actions CI/CD  ──────────────────────────────► deploy to Render
    └── Actions Cron (every 15 min) ──► Yahoo Finance / ExchangeRate API
                                                │
                                                │ gold, oil, ZAR rates
                                                ▼
                                           Supabase (PostgreSQL)
                                                ▲
                                                │ read/write
Render                                          │
    └── FastAPI web service ───────────────────►┘
              ▲  │
              │  │  HTTPS
              │  ▼
         User browser
         (dashboard · portfolio · alerts · AI chat)
```

### MCP / AI Chat Flow

The AI chat uses the **Model Context Protocol (MCP)** pattern — Groq decides which tool to call, the server executes it against Supabase, and the result feeds back to Groq for a natural language answer.

```
User asks: "What is the gold price in rands?"
         │
         ▼
FastAPI /api/chat
         │
         │  Round 1: message + tool schemas
         ▼
Groq (Llama 3.3 70B)
         │
         │  tool_call: get_latest_price(commodity="GOLD")
         ▼
FastAPI executes tool ──► Supabase (SELECT from v_latest_prices)
         │
         │  rows: { price_usd: 4407, price_zar: 75158, ... }
         ▼
         │  Round 2: message + tool result
         ▼
Groq (Llama 3.3 70B)
         │
         │  "Gold is currently R75,158 per troy oz ($4,407 USD)..."
         ▼
User sees the answer
```

---

## The MCP Pattern Explained

MCP (Model Context Protocol) is an open standard that lets an AI model call external tools during a conversation. Instead of guessing from training data, the LLM calls a real function, gets real data, and uses that to answer accurately.

Four tools are defined in `routers/chat.py`, each with a JSON schema that describes what it does and what parameters it accepts:

| Tool | What it does |
|---|---|
| `get_latest_price` | Latest gold/oil price in USD and ZAR |
| `get_price_history` | Daily averages over N days |
| `get_my_portfolio` | User's holdings with live P&L |
| `get_zar_summary` | ZAR briefing with % change vs yesterday |

The standalone `mcp_server.py` in the project exposes these same tools over stdio for direct use with Claude Desktop — the same concept, different transport layer.

---

## GitHub Actions

Two workflows run automatically from `.github/workflows/`:

### CI/CD Pipeline (`ci-cd.yml`)

Triggers on every push to `main`:

```
push to main
      │
      ├── Job 1: test
      │     Run pytest against Supabase
      │
      ├── Job 2: build
      │     Build Docker image → push to Docker Hub
      │
      └── Job 3: deploy
            POST to Render deploy webhook
```

Pull requests run only the test job — no deploy on PRs.

### Price Fetcher (`fetch-prices.yml`)

Runs on a cron schedule every 15 minutes:

```
*/15 * * * *
      │
      ├── fetch_prices.py  →  Yahoo Finance GC=F (gold), CL=F (oil)
      │                   →  ExchangeRate API (USD/ZAR)
      │                   →  INSERT into Supabase
      │
      └── check_alerts.py  →  compare prices to active user alerts
                           →  deactivate and log triggered alerts
```

GitHub Secrets required for both workflows:

| Secret | Where to get it |
|---|---|
| `SUPABASE_URL` | Supabase → Settings → API |
| `SUPABASE_ANON_KEY` | Supabase → Settings → API |
| `SUPABASE_SERVICE_KEY` | Supabase → Settings → API |
| `GROQ_API_KEY` | console.groq.com |
| `RENDER_DEPLOY_HOOK` | Render → service → Settings → Deploy Hook |

---

## Features

### Authentication & Email Verification
- Register with name, email, and password
- Supabase Auth sends a verification email automatically on signup
- Users cannot log in until email is verified
- Clicking the link calls `/api/auth/callback`, issues a JWT, redirects into the app
- Unverified login attempts redirect to the "Check your email" screen with a resend option
- Verified users see a green `✓ verified` badge in the sidebar

### Live Price Dashboard
- Gold (XAU) and WTI crude oil updated every 15 minutes via GitHub Actions
- Prices shown in both USD and ZAR
- Live USD/ZAR exchange rate
- Percentage change vs yesterday

### Personal Portfolio
- Add gold or oil holdings with quantity, buy price, and date
- Live P&L calculated in both USD and ZAR using current prices
- Total portfolio value shown in ZAR

### Price Alerts
- Set alerts for when gold or oil crosses a threshold (above or below)
- Supports USD or ZAR trigger values
- Alerts auto-deactivate when triggered and are logged

### AI Chat (MCP Pattern)
- Ask natural language questions about prices and your portfolio
- Powered by Groq Llama 3.3 70B (free API)
- LLM calls live database tools — answers are always based on real current data
- Suggested quick-access questions included

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Uvicorn |
| Database | Supabase (hosted PostgreSQL + Auth) |
| Authentication | Supabase Auth + JWT (python-jose) + bcrypt |
| AI / LLM | Groq API — Llama 3.3 70B |
| Price data | Yahoo Finance API (GC=F gold, CL=F oil) |
| FX rates | ExchangeRate API (USD/ZAR) |
| Frontend | Vanilla HTML/CSS/JS single-page app |
| CI/CD | GitHub Actions (deploy + price fetching) |
| Hosting | Render (web service + no local DB needed) |

---

## Project Structure

```
pricewatch_v4/
│
├── main.py                    # FastAPI app + router registration
├── config.py                  # Pydantic settings (reads .env)
├── auth.py                    # JWT creation + login_required dependency
├── database.py                # Supabase client (anon + admin)
├── schemas.py                 # Pydantic request/response models
│
├── routers/
│   ├── auth.py                # Register, login, email callback, /me
│   ├── prices.py              # Live prices + history (public)
│   ├── portfolio.py           # Holdings CRUD (auth required)
│   ├── alerts.py              # Alerts CRUD (auth required)
│   └── chat.py                # Groq AI chat with MCP tool calling
│
├── fetch_prices.py            # Fetches gold/oil/FX → saves to Supabase
├── check_alerts.py            # Checks and fires triggered price alerts
├── mcp_server.py              # Standalone MCP server for Claude Desktop
│
├── frontend/
│   └── index.html             # SPA: auth, dashboard, portfolio, alerts, chat
│
├── supabase_migration.sql     # Run once in Supabase SQL Editor
│
├── render.yaml                # Render Blueprint (web service)
├── .github/
│   └── workflows/
│       ├── ci-cd.yml          # Test → build → deploy pipeline
│       └── fetch-prices.yml   # Price fetch cron (every 15 min)
│
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## API Reference

Full interactive docs at `/docs` when running (auto-generated Swagger UI).

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/register` | — | Register + send verification email |
| POST | `/api/auth/login` | — | Login (verified accounts only) |
| GET | `/api/auth/callback` | — | Supabase email verification callback |
| POST | `/api/auth/resend-verification` | — | Resend verification email |
| GET | `/api/auth/me` | JWT | Current user info |
| GET | `/api/prices` | — | Latest gold/oil prices |
| GET | `/api/history/{commodity}` | — | Daily averages |
| GET | `/api/portfolio` | JWT | Holdings with live P&L |
| POST | `/api/portfolio` | JWT | Add holding |
| DELETE | `/api/portfolio/{id}` | JWT | Remove holding |
| GET | `/api/alerts` | JWT | List alerts |
| POST | `/api/alerts` | JWT | Create alert |
| DELETE | `/api/alerts/{id}` | JWT | Delete alert |
| POST | `/api/chat` | JWT | AI chat (Groq + MCP tools) |
| GET | `/health` | — | Health check |

---

## Local Setup

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/pricewatch-zar.git
cd pricewatch-zar/pricewatch_v4

# 2. Supabase — create project at supabase.com
#    SQL Editor → paste supabase_migration.sql → Run

# 3. Environment
cp .env.example .env
# Fill in: SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY,
#          JWT_SECRET, GROQ_API_KEY, APP_URL=http://localhost:8000

# 4. Install
pip install -r requirements.txt

# 5. Seed prices
python fetch_prices.py

# 6. Run
uvicorn main:app --reload
# → http://localhost:8000
# → http://localhost:8000/docs  (API docs)
```

---

## Render Deployment

```bash
git push origin main
# GitHub Actions: runs → deploys to Render automatically
```

Set these in Render dashboard → environment variables:
```
SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY,
GROQ_API_KEY, APP_URL (your Render URL)
```

Add your Render URL to Supabase → Authentication → URL Configuration:
```
https://your-app.onrender.com/api/auth/callback
```

---

## Free Services Used

| Service | Purpose | Key needed |
|---|---|---|
| Supabase | Database + Auth | Yes (free tier) |
| Groq | LLM inference | Yes (free tier) |
| Yahoo Finance | Gold + oil prices | No |
| ExchangeRate API | USD/ZAR rate | No |
| Render | Hosting | No (free tier) |
| GitHub Actions | CI/CD + price cron | No |

---

## Data Engineering Pipeline

PriceWatch ZAR implements a complete data engineering pipeline — from raw API ingestion through transformation, storage, and serving to end consumers (both the dashboard UI and the AI assistant).

```
EXTRACT                    TRANSFORM                   LOAD & SERVE
──────────────────────     ──────────────────────────  ──────────────────────────
Yahoo Finance API          Normalise price fields      INSERT into commodity_prices
  GC=F  → raw gold JSON    Convert types (str→float)   INSERT into fx_rates
  CL=F  → raw oil  JSON    Validate data present       ↓
ExchangeRate API      →    Compute ZAR values          PostgreSQL views (Supabase)
  USD/ZAR → raw FX JSON    (price_usd × usd_zar_rate)   v_prices_zar
                           Timestamp in UTC             v_latest_prices
                           Source tagging               v_daily_averages
                                                        v_portfolio_pnl
                                                        v_daily_summary
                                                        ↓
                                                       FastAPI endpoints
                                                       Groq AI tools
                                                       Browser dashboard
```

### Key data engineering patterns used

**Scheduled ingestion** — GitHub Actions runs `fetch_prices.py` on a cron schedule every 15 minutes. Each run extracts from two APIs, validates, transforms, and loads into Supabase. This is a lightweight but complete ELT pattern.

**Schema design for time-series** — `commodity_prices` and `fx_rates` are append-only tables, preserving full price history. No updates or deletes — every fetch creates a new row with a timestamp. This is standard practice for financial time-series data.

**Derived views** — raw tables are never queried directly by the application. Instead, five PostgreSQL views handle all the transformation logic: joining prices to FX rates via a lateral join (finding the nearest FX rate to each price timestamp), computing daily averages, calculating P&L against holdings, and generating ZAR summaries. Business logic lives in the database, not in application code.

**Lateral join for time-aligned FX conversion** — the key transformation in `v_prices_zar`:
```sql
join lateral (
  select rate from fx_rates
  where pair = 'USD/ZAR'
    and fetched_at <= cp.fetched_at
  order by fetched_at desc
  limit 1
) fx on true
```
This finds the most recent FX rate at or before each price timestamp — ensuring ZAR values are computed against the correct exchange rate for that moment in time, not today's rate applied retroactively.

**Alert pipeline** — `check_alerts.py` runs after every price fetch. It reads active alerts, compares against current prices, logs triggered alerts to `alert_log`, and deactivates them. This is a simple event-driven pipeline: ingest → compare → act → record.

---

## Skills Demonstrated

| Skill | Evidence |
|---|---|
| **Data engineering** | ELT pipeline, scheduled ingestion, time-series schema, lateral joins, derived views, alert pipeline |
| **Python** | FastAPI, async routes, Pydantic, JWT, bcrypt |
| **Model Context Protocol (MCP)** | Two-round tool-calling in `routers/chat.py`; standalone `mcp_server.py` |
| **PostgreSQL** | Schema design, append-only tables, 5 derived views, lateral join for FX alignment |
| **REST API design** | FastAPI routers, typed schemas, HTTP status codes |
| **Authentication** | JWT, bcrypt, Supabase Auth, full email verification flow |
| **GitHub Actions** | CI/CD pipeline + scheduled price fetching cron |
| **Cloud deployment** | Render web service, environment configuration |
| **AI integration** | Groq LLM, function/tool calling, two-round completion |
| **Financial data** | Live commodity prices, ZAR conversion, P&L calculation |

---

*BSc Mathematical Science — Python · FastAPI · Supabase · GitHub Actions · MCP · AI · Data Engineering*
