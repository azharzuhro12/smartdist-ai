"""
Security utilities for SmartDist AI.
Implements Argon2id password hashing, JWT access token generation & verification,
and Redis-backed token revocation.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.core.redis import get_redis_client

# Argon2id password hasher with RFC 9106 recommended parameters
# memory_cost=65536 KiB (64 MiB), time_cost=3 iterations, parallelism=4 lanes
_password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Hashes a plain text password using Argon2id."""
    return _password_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain text password against an Argon2id hash.
    Safely returns False if verification fails without raising exceptions.
    """
    if not hashed_password or not plain_password:
        return False
    try:
        return _password_hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    except Exception as exc:
        logger.warning(f"Unexpected error during password verification: {exc}")
        return False


def create_access_token(
    subject: Union[str, int],
    username: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
    claims: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Generates a cryptographically signed JWT access token.
    Includes subject (user_id), username, role, jti (unique ID), iat, and exp claims.
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    jti = str(uuid.uuid4())
    payload = {
        "sub": str(subject),
        "username": username,
        "role": role,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if claims:
        payload.update(claims)

    encoded_jwt = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decodes and validates a JWT access token.
    Verifies signature and expiration time.
    Returns payload dictionary if valid, None if invalid/expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": ["exp", "iat", "sub", "jti"]},
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("JWT token signature has expired.")
        return None
    except jwt.InvalidTokenError as exc:
        logger.debug(f"Invalid JWT token: {exc}")
        return None
    except Exception as exc:
        logger.warning(f"Unexpected token decoding error: {exc}")
        return None


def revoke_token(token: str, payload: Optional[Dict[str, Any]] = None) -> bool:
    """
    Revokes an active access token by placing its JTI onto the Redis revocation blocklist.
    TTL is set to the token's remaining lifetime so Redis automatically evicts expired tokens.
    """
    if not payload:
        payload = decode_access_token(token)

    if not payload:
        return False

    jti = payload.get("jti")
    exp = payload.get("exp")
    if not jti or not exp:
        return False

    now_ts = int(datetime.now(timezone.utc).timestamp())
    ttl = exp - now_ts
    if ttl <= 0:
        return True  # Already expired, no need to store

    redis_client = get_redis_client()
    if redis_client:
        try:
            redis_client.setex(f"token:blocklist:{jti}", ttl, "revoked")
            return True
        except Exception as exc:
            logger.error(f"Failed to record token revocation in Redis: {exc}")
            return False
    return False


def is_token_revoked(jti: str) -> bool:
    """
    Checks if a token JTI is present in the Redis revocation blocklist.
    """
    if not jti:
        return True
    redis_client = get_redis_client()
    if redis_client:
        try:
            return bool(redis_client.exists(f"token:blocklist:{jti}"))
        except Exception as exc:
            logger.error(f"Redis error checking token revocation: {exc}")
            return False
    return False

