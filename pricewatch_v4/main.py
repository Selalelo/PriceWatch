"""
main.py  —  PriceWatch ZAR v4
==============================
FastAPI application entry point.

Auto-generated API docs available at:
  http://localhost:8000/docs        (Swagger UI)
  http://localhost:8000/redoc       (ReDoc)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from routers import auth, prices, portfolio, alerts, chat

app = FastAPI(
    title="PriceWatch ZAR",
    description="Live gold & oil prices in ZAR with portfolios and alerts.",
    version="4.0.0",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten to your Render URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(prices.router)
app.include_router(portfolio.router)
app.include_router(alerts.router)
app.include_router(chat.router)

# ── Serve frontend SPA ────────────────────────────────────────────────────────
if os.path.exists("frontend"):
    app.mount("/static", StaticFiles(directory="frontend"), name="static")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        return FileResponse("frontend/index.html")


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "version": "4.0.0"}