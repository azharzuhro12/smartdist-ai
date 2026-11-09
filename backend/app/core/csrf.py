"""
Robust CSRF and Origin Validation for SmartDist AI.
Defends cookie-authenticated state-changing requests using:
1. Strict Origin / Referer validation against configured CORS origins.
2. Cryptographic Double-Submit CSRF cookie & header verification (constant-time).
"""

import secrets
from urllib.parse import urlparse
from typing import Optional, Set
from fastapi import Request, HTTPException, status

from backend.app.core.config import settings
from backend.app.core.logging import logger

MUTATING_METHODS: Set[str] = {"POST", "PUT", "PATCH", "DELETE"}
EXEMPT_PATHS: Set[str] = {
    f"{settings.API_V1_STR}/auth/login",
}


def generate_csrf_token() -> str:
    """Generates a cryptographically secure 32-byte hexadecimal CSRF token."""
    return secrets.token_hex(32)


def _get_normalized_origin(url_str: str) -> Optional[str]:
    """Extracts scheme://host[:port] from a full URL."""
    try:
        parsed = urlparse(url_str)
        if not parsed.scheme or not parsed.netloc:
            return None
        return f"{parsed.scheme}://{parsed.netloc}".lower()
    except Exception:
        return None


def verify_csrf_and_origin(request: Request) -> None:
    """
    Enforces Origin and CSRF validation for cookie-authenticated state-changing requests.
    Exempts Bearer-token authenticated API requests (which are immune to browser CSRF).
    """
    if request.method not in MUTATING_METHODS:
        return

    path = request.url.path
    if path in EXEMPT_PATHS:
        return

    # If client uses Authorization: Bearer <token>, browser does not send it cross-origin automatically
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer ") and len(auth_header) > 10:
        return

    # Check if request is authenticated via cookie
    cookie_token = request.cookies.get("access_token")
    if not cookie_token:
        # Not a cookie-authenticated session; auth dependencies will handle 401
        return

    # 1. Origin / Referer Validation
    allowed_origins = set()
    for origin in settings.CORS_ORIGINS:
        norm = _get_normalized_origin(origin)
        if norm:
            allowed_origins.add(norm)

    origin_header = request.headers.get("origin")
    referer_header = request.headers.get("referer")

    incoming_origin = None
    if origin_header:
        incoming_origin = _get_normalized_origin(origin_header)
    elif referer_header:
        incoming_origin = _get_normalized_origin(referer_header)

    if incoming_origin:
        if incoming_origin not in allowed_origins:
            logger.warning(
                f"CSRF blocked: incoming origin '{incoming_origin}' not in allowed CORS origins."
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF validation failed: untrusted request origin.",
            )
    elif settings.ENVIRONMENT == "production":
        # In production, state-changing cookie requests must provide Origin or Referer
        logger.warning(f"CSRF blocked: missing Origin/Referer in production on {path}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF validation failed: missing Origin or Referer header.",
        )

    # 2. Double-Submit CSRF Cookie / Header Verification
    cookie_csrf = request.cookies.get("csrf_token")
    header_csrf = request.headers.get("X-CSRF-Token") or request.headers.get("X-CSRFToken")

    if not cookie_csrf or not header_csrf:
        logger.warning(f"CSRF blocked: missing CSRF token on {path} (cookie: {bool(cookie_csrf)}, header: {bool(header_csrf)})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF validation failed: missing CSRF token cookie or X-CSRF-Token header.",
        )

    if not secrets.compare_digest(cookie_csrf, header_csrf):
        logger.warning(f"CSRF blocked: token mismatch on {path}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF validation failed: token mismatch.",
        )

