from fastapi import APIRouter
from app.api.routes import auth, problem

# Central API router. You can include sub-routers here, e.g.:
# from app.api.routes import users
# api_router.include_router(users.router, prefix="/users", tags=["users"])

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(problem.router, prefix="", tags=["problems"])