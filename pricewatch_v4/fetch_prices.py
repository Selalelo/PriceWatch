"""
fetch_prices.py  —  Live price fetcher (Supabase edition)
"""

import os
import sys
import time
import requests
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(Path(__file__).parent / ".env")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
db = create_client(SUPABASE_URL, SUPABASE_KEY)

HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch_gold() -> float | None:
    """Try multiple free gold APIs in order until one works."""

    # Source 1: Frankfurter (gold in USD via XAU/USD pair)
    try:
        r = requests.get(
            "https://api.frankfurter.app/latest?from=XAU&to=USD",
            timeout=10
        )
        r.raise_for_status()
        price = float(r.json()["rates"]["USD"])
        print(f"  [gold] source: frankfurter.app")
        return price
    except Exception as e:
        print(f"  [gold] frankfurter failed: {e}", file=sys.stderr)

    # Source 2: Yahoo Finance (GC=F is gold futures — very close to spot)
    try:
        r = requests.get(
            "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1m&range=1d",
            headers=HEADERS, timeout=10
        )
        r.raise_for_status()
        price = float(r.json()["chart"]["result"][0]["meta"]["regularMarketPrice"])
        print(f"  [gold] source: yahoo finance (GC=F)")
        return price
    except Exception as e:
        print(f"  [gold] yahoo failed: {e}", file=sys.stderr)

    # Source 3: Gold-API (free tier, 100 requests/month)
    try:
        r = requests.get(
            "https://www.goldapi.io/api/XAU/USD",
            headers={**HEADERS, "x-access-token": "goldapi-free"},
            timeout=10
        )
        r.raise_for_status()
        price = float(r.json()["price"])
        print(f"  [gold] source: goldapi.io")
        return price
    except Exception as e:
        print(f"  [gold] goldapi failed: {e}", file=sys.stderr)

    return None


def fetch_oil() -> float | None:
    try:
        r = requests.get(
            "https://query1.finance.yahoo.com/v8/finance/chart/CL=F?interval=1m&range=1d",
            headers=HEADERS, timeout=10
        )
        r.raise_for_status()
        return float(r.json()["chart"]["result"][0]["meta"]["regularMarketPrice"])
    except Exception as e:
        print(f"  [oil] {e}", file=sys.stderr)
        return None


def fetch_usd_zar() -> float | None:
    try:
        r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10)
        r.raise_for_status()
        return float(r.json()["rates"]["ZAR"])
    except Exception as e:
        print(f"  [fx] {e}", file=sys.stderr)
        return None


def run():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Fetching prices...")
    gold    = fetch_gold()
    oil     = fetch_oil()
    usd_zar = fetch_usd_zar()

    print(f"  Gold:    {'$'+f'{gold:,.2f}' if gold else 'unavailable'}")
    print(f"  Oil:     {'$'+f'{oil:,.2f}'  if oil  else 'unavailable'}")
    print(f"  USD/ZAR: {usd_zar:.4f}"      if usd_zar else "  USD/ZAR: unavailable")

    if not (usd_zar and (gold or oil)):
        print("  ⚠ Skipping save — insufficient data")
        return

    now = datetime.now(timezone.utc).isoformat()

    db.table("fx_rates").insert({
        "fetched_at": now, "pair": "USD/ZAR", "rate": usd_zar
    }).execute()

    if gold:
        db.table("commodity_prices").insert({
            "fetched_at": now, "commodity": "GOLD",
            "price_usd": gold, "unit": "troy_oz", "source": "frankfurter/yahoo"
        }).execute()
        print(f"  Gold ZAR: R{gold * usd_zar:,.2f}")

    if oil:
        db.table("commodity_prices").insert({
            "fetched_at": now, "commodity": "OIL",
            "price_usd": oil, "unit": "barrel", "source": "yahoo_finance"
        }).execute()
        print(f"  Oil ZAR:  R{oil * usd_zar:,.2f}")

    print("  ✓ Saved to Supabase")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--loop", action="store_true", help="Fetch every 15 minutes")
    args = p.parse_args()
    run()
    if args.loop:
        print("\nLoop mode — fetching every 15 min. Ctrl+C to stop.")
        try:
            while True:
                time.sleep(900)
                run()
        except KeyboardInterrupt:
            print("\nStopped.")