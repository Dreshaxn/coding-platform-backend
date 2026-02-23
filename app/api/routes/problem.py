from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.problem import (
    ProblemCreate,
    ProblemResponse,
    UserSolvedProblemResponse,
)
from app.schemas.problem_template import ProblemTemplateResponse
from app.services.problem_service import (
    ProblemServiceError,
    create_problem as create_problem_service,
    get_problem_by_id,
    get_problem_template as get_problem_template_service,
    get_problems as get_problems_service,
    get_user_solved_problems,
    solve_problem as solve_problem_service,
)

router = APIRouter()


@router.get("/problems", response_model=List[ProblemResponse])
def get_problems(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """
    Get a list of all problems
    """
    return get_problems_service(db, skip=skip, limit=limit)


@router.get("/problems/solved/me", response_model=List[ProblemResponse])
def get_my_solved_problems(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get all problems solved by the current user
    """
    return get_user_solved_problems(db, current_user.id)


@router.get("/problems/{problem_id}", response_model=ProblemResponse)
def get_problem(
    problem_id: int,
    db: Session = Depends(get_db),
):
    """
    Get details for a specific problem
    """
    try:
        return get_problem_by_id(db, problem_id)
    except ProblemServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
            headers=exc.headers,
        )


@router.post("/problems", response_model=ProblemResponse, status_code=status.HTTP_201_CREATED)
def create_problem(
    problem_data: ProblemCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new problem (MVP: open creation, admin-only later)
    """
    try:
        return create_problem_service(db, problem_data)
    except ProblemServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
            headers=exc.headers,
        )


@router.post("/problems/{problem_id}/solve", response_model=UserSolvedProblemResponse)
def solve_problem(
    problem_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Mark a problem as solved by the authenticated user
    """
    try:
        return solve_problem_service(db, problem_id, current_user.id)
    except ProblemServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
            headers=exc.headers,
        )


@router.get("/problems/{problem_id}/template", response_model=ProblemTemplateResponse)
def get_problem_template(
    problem_id: int,
    language_id: int = Query(..., description="Language ID to get the boilerplate for"),
    db: Session = Depends(get_db),
):
    """
    Get the boilerplate code template for a problem in a specific language.
    Used by the frontend to show the starter code in the editor.
    """
    try:
        return get_problem_template_service(db, problem_id, language_id)
    except ProblemServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
            headers=exc.headers,
        )
