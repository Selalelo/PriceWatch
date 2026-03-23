"""routers/chat.py  —  /api/chat  [auth required]

MCP-style context injection:
  Instead of relying on Groq's unreliable tool-call syntax, we pre-fetch
  all relevant financial data and inject it directly into the system prompt.
  The model reasons over real data without any tool call round-trips.
"""

import json
from fastapi import APIRouter, Depends
from supabase import Client
from groq import Groq

from auth import AuthUser
from config import settings
from database import get_db
from schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/api", tags=["chat"])
groq   = Groq(api_key=settings.groq_api_key)
MODEL  = "llama-3.3-70b-versatile"


def _get_context(user_id: str, db: Client) -> str:
    """
    Pre-fetch all financial context from the database and return it
    as a structured string to inject into the system prompt.
    """
    sections = []

    # ── Live prices ────────────────────────────────────────────────────────
    try:
        prices = db.table("v_latest_prices") \
                   .select("commodity,price_usd,price_zar,usd_zar_rate,unit,fetched_at") \
                   .execute().data or []
        if prices:
            lines = ["LIVE COMMODITY PRICES:"]
            for p in prices:
                lines.append(
                    f"  {p['commodity']}: ${p['price_usd']} USD | R{p['price_zar']} ZAR"
                    f" per {p.get('unit','unit')} (fetched {p.get('fetched_at','')})"
                )
            # grab usd/zar rate from first row
            rate = prices[0].get("usd_zar_rate")
            if rate:
                lines.append(f"  USD/ZAR rate: {rate}")
            sections.append("\n".join(lines))
    except Exception:
        sections.append("LIVE PRICES: unavailable")

    # ── Daily summary / % change ───────────────────────────────────────────
    try:
        summary = db.table("v_daily_summary").select("*").execute().data or []
        if summary:
            lines = ["DAILY SUMMARY (% change vs yesterday):"]
            for s in summary:
                chg = s.get("pct_change")
                chg_str = f"{float(chg):+.2f}%" if chg is not None else "N/A"
                lines.append(f"  {s.get('commodity')}: {chg_str}")
            sections.append("\n".join(lines))
    except Exception:
        pass

    # ── User portfolio ─────────────────────────────────────────────────────
    try:
        holdings = db.table("v_portfolio_pnl") \
                     .select("commodity,quantity,buy_price,current_usd,value_zar,pnl_usd,pnl_pct,label") \
                     .eq("user_id", user_id) \
                     .execute().data or []
        if holdings:
            lines = ["USER PORTFOLIO:"]
            total_zar = 0.0
            total_pnl = 0.0
            for h in holdings:
                pnl     = float(h.get("pnl_usd") or 0)
                pnl_pct = float(h.get("pnl_pct") or 0)
                val_zar = float(h.get("value_zar") or 0)
                total_zar += val_zar
                total_pnl += pnl
                label = f" [{h['label']}]" if h.get("label") else ""
                lines.append(
                    f"  {h['commodity']}{label}: {h['quantity']} units | "
                    f"bought @ ${h['buy_price']} | now ${h.get('current_usd','?')} | "
                    f"value R{val_zar:,.2f} | P&L ${pnl:+,.2f} ({pnl_pct:+.2f}%)"
                )
            lines.append(f"  TOTAL portfolio value: R{total_zar:,.2f} ZAR")
            lines.append(f"  TOTAL P&L: ${total_pnl:+,.2f} USD")
            sections.append("\n".join(lines))
        else:
            sections.append("USER PORTFOLIO: no holdings")
    except Exception:
        sections.append("USER PORTFOLIO: unavailable")

    # ── Active alerts ──────────────────────────────────────────────────────
    try:
        alerts = db.table("price_alerts") \
                   .select("commodity,direction,trigger_price,currency,is_active") \
                   .eq("user_id", user_id) \
                   .eq("is_active", True) \
                   .execute().data or []
        if alerts:
            lines = ["ACTIVE PRICE ALERTS:"]
            for a in alerts:
                lines.append(
                    f"  {a['commodity']} — alert when price goes {a['direction']} "
                    f"{a['currency']} {a['trigger_price']}"
                )
            sections.append("\n".join(lines))
        else:
            sections.append("ACTIVE ALERTS: none")
    except Exception:
        pass

    return "\n\n".join(sections)


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, current: AuthUser, db: Client = Depends(get_db)):

    # Build rich context from DB — no tool calls needed
    context = _get_context(current.user_id, db)

    system_prompt = f"""You are PriceWatch AI, a commodity analyst for South African investors.
You have access to the following real-time financial data — use it to answer accurately.
Never say you don't have access to prices or portfolio data; it is provided below.
Answer concisely in plain text. Always quote prices in both USD and ZAR where relevant.
When discussing portfolio P&L, interpret gains/losses clearly for the user.

--- CURRENT FINANCIAL CONTEXT ---
{context}
--- END CONTEXT ---
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": body.message},
    ]

    resp = groq.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=1024,
        temperature=0.3,   # lower = more factual, less creative
    )

    return {"reply": resp.choices[0].message.content}