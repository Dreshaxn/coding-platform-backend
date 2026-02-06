from fastapi import APIRouter
from app.api.routes import auth, problem, submissions

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(problem.router, prefix="", tags=["problems"])
api_router.include_router(submissions.router, prefix="", tags=["submissions"])
