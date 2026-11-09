"""
Database initialization and default admin seeding.
"""

from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.core.security import hash_password
from backend.app.models.user import User, UserRole


def init_db(db: Session) -> None:
    """
    Seeds initial system data including the default administrative account if missing.
    """
    stmt = select(User).where(User.username == settings.INITIAL_ADMIN_USERNAME)
    admin_user = db.scalar(stmt)

    if not admin_user:
        logger.info(f"Seeding default administrator account: {settings.INITIAL_ADMIN_USERNAME}")
        admin = User(
            username=settings.INITIAL_ADMIN_USERNAME,
            email=settings.INITIAL_ADMIN_EMAIL,
            hashed_password=hash_password(settings.INITIAL_ADMIN_PASSWORD),
            role=UserRole.ADMIN,
            is_active=True,
            full_name="System Administrator",
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        logger.info("Default administrator created successfully.")
    else:
        logger.debug("Default administrator account already exists.")

