"""routers/alerts.py  —  /api/alerts  [auth required]"""

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from auth import AuthUser
from database import get_db
from schemas import AlertCreate, AlertResponse

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertResponse])
def get_alerts(current: AuthUser, db: Client = Depends(get_db)):
    rows = (
        db.table("price_alerts")
        .select("*")
        .eq("user_id", current.user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return rows.data or []


@router.post("", status_code=201)
def create_alert(body: AlertCreate, current: AuthUser, db: Client = Depends(get_db)):
    row = db.table("price_alerts").insert({
        "user_id":       current.user_id,
        "commodity":     body.commodity,
        "direction":     body.direction,
        "trigger_price": body.trigger_price,
        "currency":      body.currency,
    }).execute()
    return {"id": row.data[0]["id"], "message": "Alert created"}


@router.delete("/{alert_id}")
def delete_alert(alert_id: int, current: AuthUser, db: Client = Depends(get_db)):
    existing = (
        db.table("price_alerts")
        .select("id")
        .eq("id", alert_id)
        .eq("user_id", current.user_id)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Alert not found")
    db.table("price_alerts").delete().eq("id", alert_id).execute()
    return {"message": "Alert deleted"}