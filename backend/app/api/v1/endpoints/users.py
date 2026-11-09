"""
User Administration endpoints for SmartDist AI.
Strictly restricted to users with ADMIN privileges.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.deps import require_admin
from backend.app.core.logging import logger
from backend.app.core.security import hash_password
from backend.app.db.session import get_db
from backend.app.models.user import User, UserRole
from backend.app.schemas.user import (
    UserCreate,
    UserResponse,
    UserStatusUpdateRequest,
    UserUpdate,
)

router = APIRouter()


@router.get(
    "",
    response_model=List[UserResponse],
    summary="List All System Users (Admin Only)",
)
def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Retrieves all registered system users."""
    stmt = select(User).order_by(User.id.asc())
    users = db.scalars(stmt).all()
    return [UserResponse.model_validate(u) for u in users]


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create New System User (Admin Only)",
)
def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Creates a new user account with designated role."""
    # Check duplicate username
    if db.scalar(select(User).where(User.username == user_in.username)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{user_in.username}' is already taken.",
        )

    # Check duplicate email
    if db.scalar(select(User).where(User.email == user_in.email)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email '{user_in.email}' is already registered.",
        )

    new_user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        role=UserRole(user_in.role.value),
        full_name=user_in.full_name,
        is_active=user_in.is_active,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    logger.info(f"Admin {admin.username} created new user {new_user.username} ({new_user.role.value}).")
    return UserResponse.model_validate(new_user)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get User Details by ID (Admin Only)",
)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Retrieves a specific user's record."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found.",
        )
    return UserResponse.model_validate(user)


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update User Profile & Role (Admin Only)",
)
def update_user(
    user_id: int,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Updates user information, role, or credentials."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found.",
        )

    if user_update.email and user_update.email != user.email:
        if db.scalar(select(User).where(User.email == user_update.email)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email '{user_update.email}' is already in use.",
            )
        user.email = user_update.email

    if user_update.role is not None:
        user.role = UserRole(user_update.role.value)

    if user_update.full_name is not None:
        user.full_name = user_update.full_name

    if user_update.is_active is not None:
        user.is_active = user_update.is_active

    if user_update.password is not None:
        user.hashed_password = hash_password(user_update.password)

    db.commit()
    db.refresh(user)

    logger.info(f"Admin {admin.username} updated user {user.username} (ID: {user.id}).")
    return UserResponse.model_validate(user)


@router.patch(
    "/{user_id}/status",
    response_model=UserResponse,
    summary="Activate or Deactivate User Account (Admin Only)",
)
def toggle_user_status(
    user_id: int,
    status_in: UserStatusUpdateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Enables or disables a user account."""
    if user_id == admin.id and not status_in.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot deactivate their own account.",
        )

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found.",
        )

    user.is_active = status_in.is_active
    db.commit()
    db.refresh(user)

    action = "activated" if status_in.is_active else "deactivated"
    logger.info(f"Admin {admin.username} {action} user {user.username} (ID: {user.id}).")
    return UserResponse.model_validate(user)

