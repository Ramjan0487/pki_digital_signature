"""
UC-01 · Authentication logic for GovCA login
"""
import re
import secrets
import hashlib
from datetime import datetime, timedelta

# In production this connects to GovCA's internal auth service.
# This module wraps that call with client-side pre-validation.

SESSION_STORE: dict[str, dict] = {}   # replace with Redis in production
SESSION_TTL_MINUTES = 30

RWANDA_NID_PATTERN = re.compile(r"^\d{16}$")


def authenticate_user(national_id: str, password: str) -> dict:
    """
    Validate credentials against GovCA auth endpoint.
    Returns dict with 'success', 'token' (on success), or 'error' (on failure).
    """
    # Client-side pre-validation
    if not RWANDA_NID_PATTERN.match(national_id):
        return {
            "success": False,
            "error": "National ID must be exactly 16 digits.",
            "forgot_password_url": "https://www.govca.rw/reissue/stepIndvdlReisue.sg",
        }

    if len(password) < 8:
        return {
            "success": False,
            "error": "Password must be at least 8 characters.",
            "forgot_password_url": "https://www.govca.rw/reissue/stepIndvdlReisue.sg",
        }

    # Call GovCA auth API (stubbed — replace with real HTTP call)
    auth_result = _call_govca_auth(national_id, password)

    if auth_result["status"] == "ok":
        token = _create_session(national_id)
        return {"success": True, "token": token}

    error_map = {
        "INVALID_CREDENTIALS": "Incorrect National ID or password.",
        "ACCOUNT_LOCKED":      "Account locked. Contact GovCA helpdesk.",
        "ACCOUNT_NOT_FOUND":   "No account found for this National ID.",
    }
    return {
        "success": False,
        "error": error_map.get(auth_result["status"], "Authentication failed."),
        "forgot_password_url": "https://www.govca.rw/reissue/stepIndvdlReisue.sg",
    }


def _call_govca_auth(national_id: str, password: str) -> dict:
    """Stub — replace with real GovCA auth API call."""
    # Example:
    # response = httpx.post("https://www.govca.rw/auth/api/login",
    #     json={"nationalId": national_id, "password": password}, timeout=5)
    # return response.json()
    return {"status": "ok"}   # stub always passes


def _create_session(national_id: str) -> str:
    token = secrets.token_hex(32)
    SESSION_STORE[token] = {
        "national_id": national_id,
        "expires_at": datetime.utcnow() + timedelta(minutes=SESSION_TTL_MINUTES),
    }
    return token


def validate_session(token: str) -> bool:
    session = SESSION_STORE.get(token)
    if not session:
        return False
    if datetime.utcnow() > session["expires_at"]:
        del SESSION_STORE[token]
        return False
    # Sliding window — extend on each valid use
    session["expires_at"] = datetime.utcnow() + timedelta(minutes=SESSION_TTL_MINUTES)
    return True
