"""Problem service utilities for managing problems and solutions."""
from http import HTTPStatus
from typing import List, Optional

from sqlalchemy.orm import Session, joinedload

from app.models.problem import Problem
from app.models.category import Category
from app.models.difficulty import Difficulty
from app.models.user_solved_problem import UserSolvedProblem
from app.schemas.problem import ProblemCreate


class ProblemServiceError(Exception):
    """Domain-level error that can be translated into an HTTP exception."""

    def __init__(
        self, *, status_code: int, detail: str, headers: Optional[dict] = None
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.headers = headers
        super().__init__(detail)


def get_problems(db: Session, skip: int = 0, limit: int = 100) -> List[Problem]:
    """
    Get a list of all problems with relationships loaded.
    """
    return (
        db.query(Problem)
        .options(
            joinedload(Problem.category),
            joinedload(Problem.difficulty)
        )
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_problem_by_id(db: Session, problem_id: int) -> Problem:
    """
    Get a problem by ID with relationships loaded.
    Raises ProblemServiceError if not found.
    """
    problem = (
        db.query(Problem)
        .options(
            joinedload(Problem.category),
            joinedload(Problem.difficulty)
        )
        .filter(Problem.id == problem_id)
        .first()
    )
    
    if not problem:
        raise ProblemServiceError(
            status_code=HTTPStatus.NOT_FOUND.value,
            detail="Problem not found"
        )
    
    return problem


def create_problem(db: Session, problem_data: ProblemCreate) -> Problem:
    """
    Create a new problem.
    Raises ProblemServiceError if validation fails.
    """
    # Verify category exists
    category = db.query(Category).filter(Category.id == problem_data.category_id).first()
    if not category:
        raise ProblemServiceError(
            status_code=HTTPStatus.NOT_FOUND.value,
            detail="Category not found"
        )
    
    # Verify difficulty exists
    difficulty = db.query(Difficulty).filter(Difficulty.id == problem_data.difficulty_id).first()
    if not difficulty:
        raise ProblemServiceError(
            status_code=HTTPStatus.NOT_FOUND.value,
            detail="Difficulty not found"
        )
    
    # Check if title already exists
    existing_problem = db.query(Problem).filter(Problem.title == problem_data.title).first()
    if existing_problem:
        raise ProblemServiceError(
            status_code=HTTPStatus.BAD_REQUEST.value,
            detail="Problem with this title already exists"
        )
    
    # Create new problem
    new_problem = Problem(
        title=problem_data.title,
        description=problem_data.description,
        difficulty_id=problem_data.difficulty_id,
        category_id=problem_data.category_id,
    )
    
    db.add(new_problem)
    db.commit()
    db.refresh(new_problem)
    
    # Reload with relationships
    return get_problem_by_id(db, new_problem.id)


def solve_problem(db: Session, problem_id: int, user_id: int) -> UserSolvedProblem:
    """
    Mark a problem as solved by a user.
    Raises ProblemServiceError if validation fails.
    """
    # Verify problem exists
    problem = db.query(Problem).filter(Problem.id == problem_id).first()
    if not problem:
        raise ProblemServiceError(
            status_code=HTTPStatus.NOT_FOUND.value,
            detail="Problem not found"
        )
    
    # Check if already solved
    existing_solution = (
        db.query(UserSolvedProblem)
        .filter(
            UserSolvedProblem.user_id == user_id,
            UserSolvedProblem.problem_id == problem_id
        )
        .first()
    )
    
    if existing_solution:
        raise ProblemServiceError(
            status_code=HTTPStatus.BAD_REQUEST.value,
            detail="Problem already solved by this user"
        )
    
    # Create new solution record
    new_solution = UserSolvedProblem(
        user_id=user_id,
        problem_id=problem_id,
    )
    
    db.add(new_solution)
    db.commit()
    db.refresh(new_solution)
    
    return new_solution


def get_user_solved_problems(db: Session, user_id: int) -> List[Problem]:
    """
    Get all problems solved by a specific user.
    """
    return (
        db.query(Problem)
        .join(UserSolvedProblem)
        .filter(UserSolvedProblem.user_id == user_id)
        .options(
            joinedload(Problem.category),
            joinedload(Problem.difficulty)
        )
        .all()
    )

