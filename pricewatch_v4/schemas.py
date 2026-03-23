"""
schemas.py  —  Pydantic models
All request bodies and response shapes live here.
FastAPI uses these for automatic validation + OpenAPI docs.
"""

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator


# ── Auth ──────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email:     EmailStr
    password:  str
    full_name: Optional[str] = None

    @field_validator("password")
    @classmethod
    def password_length(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email:    EmailStr
    password: str


class TokenResponse(BaseModel):
    token: str
    user:  dict


class UserResponse(BaseModel):
    id:         str
    email:      str
    full_name:  Optional[str]
    created_at: Optional[datetime]


# ── Portfolio ─────────────────────────────────────────────────────────────────

class HoldingCreate(BaseModel):
    commodity: str
    quantity:  float
    buy_price: float
    buy_date:  date
    label:     Optional[str] = None

    @field_validator("commodity")
    @classmethod
    def valid_commodity(cls, v):
        if v.upper() not in ("GOLD", "OIL"):
            raise ValueError("Commodity must be GOLD or OIL")
        return v.upper()

    @field_validator("quantity", "buy_price")
    @classmethod
    def positive(cls, v):
        if v <= 0:
            raise ValueError("Must be greater than zero")
        return v


class HoldingResponse(BaseModel):
    id:          int
    commodity:   str
    quantity:    float
    buy_price:   float
    buy_date:    date
    label:       Optional[str]
    current_usd: Optional[float]
    current_zar: Optional[float]
    value_usd:   Optional[float]
    value_zar:   Optional[float]
    pnl_usd:     Optional[float]
    pnl_pct:     Optional[float]


class PortfolioResponse(BaseModel):
    holdings:        list[HoldingResponse]
    total_value_zar: float
    total_pnl_usd:   float


# ── Alerts ────────────────────────────────────────────────────────────────────

class AlertCreate(BaseModel):
    commodity:     str
    direction:     str
    trigger_price: float
    currency:      str = "USD"

    @field_validator("commodity")
    @classmethod
    def valid_commodity(cls, v):
        if v.upper() not in ("GOLD", "OIL"):
            raise ValueError("Commodity must be GOLD or OIL")
        return v.upper()

    @field_validator("direction")
    @classmethod
    def valid_direction(cls, v):
        if v not in ("above", "below"):
            raise ValueError("Direction must be 'above' or 'below'")
        return v

    @field_validator("currency")
    @classmethod
    def valid_currency(cls, v):
        if v.upper() not in ("USD", "ZAR"):
            raise ValueError("Currency must be USD or ZAR")
        return v.upper()


class AlertResponse(BaseModel):
    id:            int
    commodity:     str
    direction:     str
    trigger_price: float
    currency:      str
    is_active:     bool
    triggered_at:  Optional[datetime]
    created_at:    Optional[datetime]


# ── Prices ────────────────────────────────────────────────────────────────────

class PriceRow(BaseModel):
    commodity:    str
    price_usd:    float
    price_zar:    float
    usd_zar_rate: float
    unit:         str
    fetched_at:   Optional[datetime]


class PriceSummary(BaseModel):
    commodity:   str
    avg_usd:     float
    avg_zar:     float
    pct_change:  Optional[float]


class PricesResponse(BaseModel):
    latest:  list[PriceRow]
    summary: list[PriceSummary]


# ── Chat ──────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str