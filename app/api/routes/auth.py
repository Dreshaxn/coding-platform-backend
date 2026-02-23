from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.auth import RefreshTokenRequest, Token, UserLogin
from app.schemas.user import UserCreate, UserResponse
from app.services.token_service import (
    AuthServiceError,
    login_user as login_user_service,
    refresh_access_token as refresh_access_token_service,
    register_user as register_user_service,
    revoke_refresh_token,
)

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user
    """
    try:
        new_user = register_user_service(db, user_data)
        return new_user
    except AuthServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
            headers=exc.headers,
        )


@router.post("/login", response_model=Token)
def login(user_data: UserLogin, db: Session = Depends(get_db)):
    """
    Login user and return JWT token
    """
    try:
        tokens = login_user_service(db, user_data)
    except AuthServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
            headers=exc.headers,
        )

    return Token(**tokens)


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user information
    """
    return current_user

@router.post("/refresh", response_model=Token)
def refresh_token(data: RefreshTokenRequest, db: Session = Depends(get_db)):
    """
    Refresh access token using a valid refresh token
    """
    try:
        tokens = refresh_access_token_service(db, data.refresh_token)
    except AuthServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
            headers=exc.headers,
        )

    return Token(**tokens)


@router.post("/logout")
def logout(data: RefreshTokenRequest, db: Session = Depends(get_db)):
    """
    Revoke refresh token
    """
    try:
        revoke_refresh_token(db, data.refresh_token)
        return {"success": True}
    except AuthServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
            headers=exc.headers,
        )