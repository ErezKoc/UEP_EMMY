"""Shared FastAPI dependencies (who is calling, and may they).

Add `current_user: User = Depends(get_current_user)` to any route that needs the
signed-in user, `Depends(get_optional_user)` where anonymous access is still
allowed, or `Depends(get_current_admin)` for admin-only routes.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import verify_token
from app.db.session import get_db
from app.models import User, UserRole

_bearer = HTTPBearer(auto_error=False)


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User | None:
    """Resolve the user from the Bearer token, or None when absent/invalid."""
    if credentials is None:
        return None
    user_id = verify_token(credentials.credentials)
    if user_id is None:
        return None
    return db.get(User, user_id)


def get_current_user(user: User | None = Depends(get_optional_user)) -> User:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    """Admin-only routes (403 when signed in as a non-admin)."""
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required.",
        )
    return user


def suspension_message(user: User) -> str:
    """Explain a restriction to the account it applies to."""
    if user.is_banned:
        base = "Your account has been banned for violating the community rules."
    elif user.suspended_until is None:
        base = "Your account is suspended."
    else:
        base = f"Your account is suspended until {user.suspended_until:%d %b %Y}."
    return f"{base} {user.moderation_note}" if user.moderation_note else base


def get_active_user(user: User = Depends(get_current_user)) -> User:
    """Routes that write to the community.

    Reading stays open to suspended and banned accounts so they can still see
    the platform and the reason for the restriction; only participation stops.
    """
    if not user.can_participate:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=suspension_message(user)
        )
    return user
