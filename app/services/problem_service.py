from http import HTTPStatus
from typing import List, Optional

from sqlalchemy.orm import Session, joinedload

from app.models.problem import Problem
from app.models.problem_template import ProblemTemplate
from app.models.category import Category
from app.models.difficulty import Difficulty
from app.models.user_solved_problem import UserSolvedProblem
from app.schemas.problem import ProblemCreate
from app.cache.redis import cache_get_sync, cache_set_sync, cache_delete_sync


class ProblemServiceError(Exception):
    def __init__(
        self, *, status_code: int, detail: str, headers: Optional[dict] = None
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.headers = headers
        super().__init__(detail)


def _problem_to_cache_dict(problem: Problem) -> dict:
    return {
        "id": problem.id,
        "title": problem.title,
        "description": problem.description,
        "difficulty_id": problem.difficulty_id,
        "category_id": problem.category_id,
        "function_name": problem.function_name,
    }


def get_problems(db: Session, skip: int = 0, limit: int = 100) -> List[Problem]:
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
    We need the full ORM object with joined relationships for the response,
    so the cache here is write-through: every fetch warms the cache for
    other services (like judge_queue) that only need the raw fields.
    """
    cache_key = f"cache:problem:{problem_id}"
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

    cache_set_sync(cache_key, _problem_to_cache_dict(problem), ttl=300)
    return problem


def create_problem(db: Session, problem_data: ProblemCreate) -> Problem:
    category = db.query(Category).filter(Category.id == problem_data.category_id).first()
    if not category:
        raise ProblemServiceError(
            status_code=HTTPStatus.NOT_FOUND.value,
            detail="Category not found"
        )

    difficulty = db.query(Difficulty).filter(Difficulty.id == problem_data.difficulty_id).first()
    if not difficulty:
        raise ProblemServiceError(
            status_code=HTTPStatus.NOT_FOUND.value,
            detail="Difficulty not found"
        )

    existing_problem = db.query(Problem).filter(Problem.title == problem_data.title).first()
    if existing_problem:
        raise ProblemServiceError(
            status_code=HTTPStatus.BAD_REQUEST.value,
            detail="Problem with this title already exists"
        )

    new_problem = Problem(
        title=problem_data.title,
        description=problem_data.description,
        difficulty_id=problem_data.difficulty_id,
        category_id=problem_data.category_id,
        function_name=problem_data.function_name,
    )

    db.add(new_problem)
    db.commit()
    db.refresh(new_problem)

    return get_problem_by_id(db, new_problem.id)


def solve_problem(db: Session, problem_id: int, user_id: int) -> UserSolvedProblem:
    problem = db.query(Problem).filter(Problem.id == problem_id).first()
    if not problem:
        raise ProblemServiceError(
            status_code=HTTPStatus.NOT_FOUND.value,
            detail="Problem not found"
        )

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

    new_solution = UserSolvedProblem(
        user_id=user_id,
        problem_id=problem_id,
    )

    db.add(new_solution)
    db.commit()
    db.refresh(new_solution)

    return new_solution


def get_user_solved_problems(db: Session, user_id: int) -> List[Problem]:
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


def get_problem_template(db: Session, problem_id: int, language_id: int) -> ProblemTemplate:
    template = (
        db.query(ProblemTemplate)
        .filter(
            ProblemTemplate.problem_id == problem_id,
            ProblemTemplate.language_id == language_id,
        )
        .first()
    )
    if not template:
        raise ProblemServiceError(
            status_code=HTTPStatus.NOT_FOUND.value,
            detail="No template found for this problem/language combination",
        )
    return template
