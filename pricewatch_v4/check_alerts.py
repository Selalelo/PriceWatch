"""
check_alerts.py  —  Price alert checker (Supabase edition)
===========================================================
Runs after every price fetch. Fires triggered alerts.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")
import sys
from datetime import datetime, timezone
from supabase import create_client

db = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


def check():
    alerts = db.table("price_alerts").select(
        "id, user_id, commodity, direction, trigger_price, currency, users(email, full_name)"
    ).eq("is_active", True).execute().data or []

    if not alerts:
        print("  No active alerts."); return

    prices = {
        r["commodity"]: r for r in
        db.table("v_latest_prices").select("commodity, price_usd, price_zar").execute().data or []
    }

    triggered = 0
    for a in alerts:
        p = prices.get(a["commodity"])
        if not p: continue

        current = float(p["price_zar"]) if a["currency"] == "ZAR" else float(p["price_usd"])
        trigger = float(a["trigger_price"])
        fired   = (a["direction"] == "above" and current >= trigger) or \
                  (a["direction"] == "below" and current <= trigger)

        if fired:
            sym = "R" if a["currency"] == "ZAR" else "$"
            msg = (f"{a['commodity']} is {a['direction']} {sym}{trigger:,.2f} "
                   f"(now: {sym}{current:,.2f} {a['currency']})")
            print(f"  TRIGGERED: {msg}")

            db.table("alert_log").insert({
                "alert_id": a["id"], "user_id": a["user_id"],
                "commodity": a["commodity"], "price_usd": float(p["price_usd"]), "message": msg
            }).execute()

            db.table("price_alerts").update({
                "is_active": False,
                "triggered_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", a["id"]).execute()

            triggered += 1

    print(f"  Checked {len(alerts)} alerts — {triggered} triggered.")


if __name__ == "__main__":
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Checking alerts...")
    try:
        check()
    except Exception as e:
        print(f"  ERROR: {e}", file=sys.stderr)
        sys.exit(1)