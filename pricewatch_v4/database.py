"""
database.py  —  Supabase client
================================
Wraps the supabase-py client so the rest of the app
just calls  db.table("name").select(...)  etc.

We use the SERVICE KEY for server-side operations
(bypasses Supabase RLS — we enforce auth ourselves via JWT).
"""

from supabase import create_client, Client
from config import settings

# ── Two clients ───────────────────────────────────────────────────────────────
# anon_client  — use for public reads (prices)
# admin_client — use for all writes and protected reads (bypasses RLS)

anon_client: Client  = create_client(settings.supabase_url, settings.supabase_anon_key)
admin_client: Client = create_client(settings.supabase_url, settings.supabase_service_key)


def get_db() -> Client:
    """FastAPI dependency — yields the admin client."""
    return admin_client