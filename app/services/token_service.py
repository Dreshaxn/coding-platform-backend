"""Authentication service utilities for issuing and refreshing tokens."""
from http import HTTPStatus
from typing import Dict, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.auth import UserLogin
from app.schemas.user import UserCreate
from app.services.auth import (
    hash_password,
    hash_refresh_token,
    verify_password,
    verify_refresh_token,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_token,
)


class AuthServiceError(Exception):
    """Domain-level error that can be translated into an HTTP exception."""

    def __init__(
        self, *, status_code: int, detail: str, headers: Optional[Dict[str, str]] = None
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.headers = headers
        super().__init__(detail)


def login_user(db: Session, credentials: UserLogin) -> Dict[str, str]:
    """
    Authenticate a user and return newly issued tokens.
    Raises AuthServiceError when authentication fails.
    """
    user = _find_user_by_identifier(db, credentials.email, credentials.username)
    if not user:
        raise AuthServiceError(
            status_code=HTTPStatus.UNAUTHORIZED.value,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(credentials.password, user.hashed_password):
        raise AuthServiceError(
            status_code=HTTPStatus.UNAUTHORIZED.value,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise AuthServiceError(
            status_code=HTTPStatus.FORBIDDEN.value,
            detail="Inactive user",
        )

    return _issue_tokens_for_user(db, user)


def refresh_access_token(db: Session, refresh_token: str) -> Dict[str, str]:
    """
    Validate the refresh token and issue a new access token.
    Raises AuthServiceError when validation fails.
    """
    payload = verify_token(refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise AuthServiceError(
            status_code=HTTPStatus.UNAUTHORIZED.value,
            detail="Invalid refresh token",
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise AuthServiceError(
            status_code=HTTPStatus.UNAUTHORIZED.value,
            detail="Invalid refresh token payload",
        )

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise AuthServiceError(
            status_code=HTTPStatus.NOT_FOUND.value,
            detail="User not found",
        )

    if not user.refresh_token_hash or not verify_refresh_token(
        user.refresh_token_hash, refresh_token
    ):
        raise AuthServiceError(
            status_code=HTTPStatus.UNAUTHORIZED.value,
            detail="Invalid or revoked refresh token",
        )

    access_token = create_access_token({"sub": str(user.id)})
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


def _find_user_by_identifier(
    db: Session, email: Optional[str], username: Optional[str]
) -> Optional[User]:
    """Return a user either by email or username."""
    query = db.query(User)
    if email:
        return query.filter(User.email == email).first()
    if username:
        return query.filter(User.username == username).first()
    return None


def register_user(db: Session, user_data: UserCreate) -> User:
    """
    Register a new user.
    Raises AuthServiceError if email or username already exists.
    """
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise AuthServiceError(
            status_code=HTTPStatus.BAD_REQUEST.value,
            detail="Email already registered",
        )

    # Check if username already exists
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise AuthServiceError(
            status_code=HTTPStatus.BAD_REQUEST.value,
            detail="Username already taken",
        )

    # Hash the password and create new user
    hashed_password = hash_password(user_data.password)
    new_user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password,
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user
    except IntegrityError:
        db.rollback()
        raise AuthServiceError(
            status_code=HTTPStatus.BAD_REQUEST.value,
            detail="User could not be created. Email or username may already exist.",
        )


def _issue_tokens_for_user(db: Session, user: User) -> Dict[str, str]:
    """Create tokens for the provided user and persist refresh token hash."""
    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    user.refresh_token_hash = hash_refresh_token(refresh_token)
    db.commit()
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }

