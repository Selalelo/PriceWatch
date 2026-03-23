"""routers/auth.py  —  /api/auth/*

Auth flows supported:
  ① Email/password
      1. POST /register  → Supabase creates user + sends verification email
      2. User clicks link → Supabase → GET /callback?token_hash=...&type=email
      3. GET /callback   → verifies OTP, issues JWT, redirects to /#verified
      4. POST /login     → checks email_confirmed_at, issues JWT

  ② Google OAuth
      1. GET  /google    → returns {url} — the Supabase-generated Google consent URL
      2. Browser redirects user to Google, user consents
      3. Google → Supabase → GET /callback?code=...&type=... (same callback endpoint)
      4. GET /callback   → exchanges code for session, issues JWT, redirects to /#verified
"""

from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.responses import RedirectResponse
from supabase import Client

from auth import create_access_token, AuthUser
from config import settings
from database import get_db
from schemas import RegisterRequest, LoginRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ── helpers ────────────────────────────────────────────────────────────────────

def _upsert_user(db: Client, email: str, full_name: str = "") -> dict:
    """Return our users-table row, creating it if it doesn't exist yet."""
    rows = db.table("users").select("id,email,full_name").eq("email", email).execute()
    if rows.data:
        return rows.data[0]
    row = db.table("users").insert({
        "email":         email,
        "password_hash": "",        # Supabase Auth owns the credential
        "full_name":     full_name,
    }).execute()
    return row.data[0]


def _mark_verified(db: Client, email: str) -> None:
    db.table("users").update({"email_verified": True}).eq("email", email).execute()


# ── register ───────────────────────────────────────────────────────────────────

@router.post("/register", status_code=201)
def register(body: RegisterRequest, db: Client = Depends(get_db)):
    """
    Create account via Supabase Auth — sends a verification email automatically.
    No JWT is issued until the user clicks the link.
    """
    try:
        res = db.auth.sign_up({
            "email":    body.email,
            "password": body.password,
            "options": {
                "data": {"full_name": body.full_name or ""},
                "email_redirect_to": f"{settings.app_url}/api/auth/callback",
            },
        })
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))

    if res.user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Registration failed")

    _upsert_user(db, body.email, body.full_name or "")

    return {
        "message": "Registration successful. Please check your email and click the verification link.",
        "email": body.email,
    }


# ── Google OAuth ───────────────────────────────────────────────────────────────

@router.get("/google")
def google_oauth(db: Client = Depends(get_db)):
    """
    Return the Supabase-generated Google OAuth URL.
    The frontend redirects the browser there; Google authenticates the user
    and bounces them back via Supabase → our /callback endpoint.
    """
    try:
        res = db.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {
                "redirect_to": f"{settings.app_url}/api/auth/callback",
                # Request profile + email scopes (Supabase default, shown for clarity)
                "scopes": "openid email profile",
            },
        })
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    if not res or not getattr(res, "url", None):
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not generate Google OAuth URL",
        )

    return {"url": res.url}


# ── shared callback ────────────────────────────────────────────────────────────

@router.get("/callback")
def auth_callback(request: Request, db: Client = Depends(get_db)):
    """
    Unified callback for both email-verification links and Google OAuth.

    Supabase appends different query params depending on the flow:
      • Email link  → ?token_hash=<hash>&type=email
      • Google OAuth → ?code=<code>&type=... (Supabase PKCE) — but Supabase JS SDK
                       also sends the session in the URL hash, which we handle on
                       the frontend.  For the server-side PKCE flow Supabase uses
                       ?code=... which we exchange via exchange_code_for_session().
    """
    params     = request.query_params
    token_hash = params.get("token_hash")
    code       = params.get("code")

    # ── Google / PKCE code exchange ──────────────────────────────────────────
    if code:
        try:
            res = db.auth.exchange_code_for_session({"auth_code": code})
        except Exception:
            return RedirectResponse(url="/#verify-failed")

        if not res or not res.user:
            return RedirectResponse(url="/#verify-failed")

        email     = res.user.email
        full_name = (res.user.user_metadata or {}).get("full_name", "") or \
                    (res.user.user_metadata or {}).get("name", "")

        _mark_verified(db, email)
        user  = _upsert_user(db, email, full_name)
        token = create_access_token(str(user["id"]), user["email"])
        return RedirectResponse(
            url=f"/#verified?token={token}&name={user['full_name']}&email={user['email']}&id={user['id']}"
        )

    # ── Email OTP / magic-link verification ──────────────────────────────────
    if token_hash:
        type_ = params.get("type", "email")
        try:
            res = db.auth.verify_otp({"token_hash": token_hash, "type": type_})
        except Exception:
            return RedirectResponse(url="/#verify-failed")

        if not res or not res.user:
            return RedirectResponse(url="/#verify-failed")

        email = res.user.email
        _mark_verified(db, email)
        user  = _upsert_user(db, email,
                             (res.user.user_metadata or {}).get("full_name", ""))
        token = create_access_token(str(user["id"]), user["email"])
        return RedirectResponse(
            url=f"/#verified?token={token}&name={user['full_name']}&email={user['email']}&id={user['id']}"
        )

    # Nothing we can handle
    return RedirectResponse(url="/#verify-failed")


# ── login ──────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Client = Depends(get_db)):
    """Email + password login. Blocks unverified accounts."""
    try:
        res = db.auth.sign_in_with_password({
            "email":    body.email,
            "password": body.password,
        })
    except Exception as e:
        err = str(e).lower()
        if "email not confirmed" in err:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="Please verify your email before logging in. Check your inbox.",
            )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if not res.user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    user  = _upsert_user(db, body.email,
                         res.user.user_metadata.get("full_name", ""))
    token = create_access_token(str(user["id"]), user["email"])
    return {
        "token": token,
        "user":  {"id": user["id"], "email": user["email"], "full_name": user["full_name"]},
    }


# ── resend verification ────────────────────────────────────────────────────────

@router.post("/resend-verification")
def resend_verification(body: LoginRequest, db: Client = Depends(get_db)):
    """Resend the email-verification link."""
    try:
        db.auth.resend({
            "type":  "signup",
            "email": body.email,
            "options": {"email_redirect_to": f"{settings.app_url}/api/auth/callback"},
        })
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"message": "Verification email resent. Please check your inbox."}


# ── me ─────────────────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
def me(current: AuthUser, db: Client = Depends(get_db)):
    rows = db.table("users").select("id,email,full_name,created_at").eq("id", current.user_id).execute()
    if not rows.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    return rows.data[0]