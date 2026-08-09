from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, suspension_message
from app.core.security import create_token, hash_password, verify_password
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas import AuthResponse, CurrentUserRead, LoginRequest, SignupRequest

router = APIRouter()


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> AuthResponse:
    email = payload.email.lower()
    exists = db.scalars(select(User).where(func.lower(User.email) == email)).first()
    if exists is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    is_vet = payload.role == UserRole.VETERINARIAN
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        role=payload.role,
        clinic_name=payload.clinic_name if is_vet else None,
        license_number=payload.license_number if is_vet else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return AuthResponse(token=create_token(user.id), user=CurrentUserRead.model_validate(user))


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    email = payload.email.lower()
    user = db.scalars(select(User).where(func.lower(User.email) == email)).first()
    # Same error for "no such user" and "wrong password" so the endpoint
    # doesn't reveal which emails are registered.
    if (
        user is None
        or user.password_hash is None
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )
    # A ban ends access entirely; a suspension still allows signing in so the
    # member can read the reason and wait it out.
    if user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=suspension_message(user))
    return AuthResponse(token=create_token(user.id), user=CurrentUserRead.model_validate(user))


@router.get("/me", response_model=CurrentUserRead)
def me(current_user: User = Depends(get_current_user)) -> User:
    """Return the user for the presented token (used to restore sessions)."""
    return current_user
