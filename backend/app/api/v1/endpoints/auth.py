"""
Authentication endpoints for SmartDist AI.
Implements login (JSON/Form), token revocation logout, and current user profile retrieval.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.app.api.deps import (
    get_current_active_user,
    get_token_from_request,
)
from backend.app.core.config import settings
from backend.app.core.csrf import generate_csrf_token
from backend.app.core.logging import logger
from backend.app.core.rate_limit import check_rate_limit, get_client_ip
from backend.app.core.security import (
    create_access_token,
    revoke_token,
    verify_password,
)
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.schemas.user import LoginRequest, TokenResponse, UserResponse

router = APIRouter()


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate User & Issue Access Token",
)
def login(
    request: Request,
    response: Response,
    login_data: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    Authenticates system users with username or email and password.
    Returns JWT access token and sets an HttpOnly Secure cookie for browser sessions.
    Strictly rate limited to mitigate brute force credential attacks.
    """
    client_ip = get_client_ip(request)
    check_rate_limit(
        f"login:{client_ip}",
        max_requests=settings.RATE_LIMIT_LOGIN_PER_MINUTE,
        window_seconds=60,
        fail_closed=True,
    )

    stmt = select(User).where(
        or_(
            User.username == login_data.username_or_email,
            User.email == login_data.username_or_email,
        )
    )
    user = db.scalar(stmt)

    # Generic failure response to prevent user account enumeration
    if not user or not verify_password(login_data.password, user.hashed_password):
        logger.warning(f"Failed login attempt for identifier: {login_data.username_or_email} from {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        logger.warning(f"Login attempted on inactive account: {user.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Issue access token
    access_token = create_access_token(
        subject=user.id,
        username=user.username,
        role=user.role.value,
    )

    # Set secure HttpOnly cookie for browser sessions
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=(settings.ENVIRONMENT == "production"),
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )

    # Set non-HttpOnly CSRF cookie for browser double-submit verification
    csrf_token = generate_csrf_token()
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,  # JavaScript must read this to attach X-CSRF-Token header
        samesite="lax",
        secure=(settings.ENVIRONMENT == "production"),
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )

    logger.info(f"User {user.username} ({user.role.value}) logged in successfully from {client_ip}.")

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get Current Authenticated User Profile",
)
def get_me(current_user: User = Depends(get_current_active_user)):
    """Returns the profile of the currently authenticated active user."""
    return UserResponse.model_validate(current_user)


@router.post(
    "/logout",
    summary="Revoke Token & Terminate Session",
)
def logout(
    response: Response,
    token: str = Depends(get_token_from_request),
    current_user: User = Depends(get_current_active_user),
):
    """
    Terminates session by placing access token on the Redis revocation blocklist
    and clearing the browser authentication cookie.
    """
    if token:
        revoke_token(token)

    response.delete_cookie(
        key="access_token",
        path="/",
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        key="csrf_token",
        path="/",
        httponly=False,
        samesite="lax",
    )

    logger.info(f"User {current_user.username} logged out; token revoked.")
    return {"message": "Successfully logged out. Session terminated."}

