"""routers/prices.py  —  /api/prices  (public)"""

from fastapi import APIRouter, Depends, Query
from supabase import Client

from database import get_db
from schemas import PricesResponse

router = APIRouter(prefix="/api", tags=["prices"])


@router.get("/prices", response_model=PricesResponse)
def get_prices(db: Client = Depends(get_db)):
    latest  = db.table("v_latest_prices").select("*").execute().data or []
    summary = db.table("v_daily_summary").select("*").execute().data or []
    return {"latest": latest, "summary": summary}


@router.get("/history/{commodity}")
def get_history(
    commodity: str,
    days: int = Query(default=7, ge=1, le=90),
    db: Client = Depends(get_db)
):
    rows = (
        db.table("v_daily_averages")
        .select("price_date,avg_usd,avg_zar,samples")
        .eq("commodity", commodity.upper())
        .order("price_date", desc=False)
        .limit(days)
        .execute()
    )
    return rows.data or []