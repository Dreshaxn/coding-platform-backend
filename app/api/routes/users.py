from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.user import UserMeResponse

router = APIRouter()


@router.get("/users/me", response_model=UserMeResponse)
def get_user(current_user: User = Depends(get_current_user)) -> UserMeResponse:
    return current_user
