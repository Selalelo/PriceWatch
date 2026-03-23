"""routers/portfolio.py  —  /api/portfolio  [auth required]"""

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from auth import AuthUser
from database import get_db
from schemas import HoldingCreate, HoldingResponse, PortfolioResponse

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("", response_model=PortfolioResponse)
def get_portfolio(current: AuthUser, db: Client = Depends(get_db)):
    rows = (
        db.table("v_portfolio_pnl")
        .select("*")
        .eq("user_id", current.user_id)
        .order("buy_date", desc=True)
        .execute()
    )
    holdings        = rows.data or []
    total_value_zar = sum(float(h.get("value_zar") or 0) for h in holdings)
    total_pnl_usd   = sum(float(h.get("pnl_usd")   or 0) for h in holdings)
    return {
        "holdings":        holdings,
        "total_value_zar": round(total_value_zar, 2),
        "total_pnl_usd":   round(total_pnl_usd,   2),
    }


@router.post("", status_code=201)
def add_holding(body: HoldingCreate, current: AuthUser, db: Client = Depends(get_db)):
    row = db.table("portfolio_holdings").insert({
        "user_id":   current.user_id,
        "commodity": body.commodity,
        "quantity":  body.quantity,
        "buy_price": body.buy_price,
        "buy_date":  body.buy_date.isoformat(),
        "label":     body.label or "",
    }).execute()
    return {"id": row.data[0]["id"], "message": "Holding added"}


@router.delete("/{holding_id}")
def delete_holding(holding_id: int, current: AuthUser, db: Client = Depends(get_db)):
    existing = (
        db.table("portfolio_holdings")
        .select("id")
        .eq("id", holding_id)
        .eq("user_id", current.user_id)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Holding not found")
    db.table("portfolio_holdings").delete().eq("id", holding_id).execute()
    return {"message": "Holding removed"}