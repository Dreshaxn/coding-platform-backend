from http import HTTPStatus
import logging
from typing import List, Optional

from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from app.models.problem import Problem
from app.models.problem_template import ProblemTemplate
from app.models.user_solved_problem import UserSolvedProblem
from app.repositories.problem_repository import (
    CategoryRepository,
    DifficultyRepository,
    ProblemRepository,
    ProblemTemplateRepository,
    UserSolvedProblemRepository,
)
from app.schemas.problem import ProblemCreate
from app.cache.redis import cache_set_sync

logger = logging.getLogger(__name__)


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
    return ProblemRepository(db).list(skip=skip, limit=limit)


def get_problem_by_id(db: Session, problem_id: int) -> Problem:
    """
    We need the full ORM object with joined relationships for the response,
    so the cache here is write-through: every fetch warms the cache for
    other services (like judge_queue) that only need the raw fields.
    """
    cache_key = f"cache:problem:{problem_id}"
    problem = ProblemRepository(db).get_with_details(problem_id)

    if not problem:
        raise ProblemServiceError(
            status_code=HTTPStatus.NOT_FOUND.value,
            detail="Problem not found"
        )

    try:
        cache_set_sync(cache_key, _problem_to_cache_dict(problem), ttl=300)
    except RedisError as exc:
        logger.warning(
            "Problem cache set failed problem_id=%s error=%s",
            problem_id,
            exc,
        )
    return problem


def create_problem(db: Session, problem_data: ProblemCreate) -> Problem:
    problems = ProblemRepository(db)
    function_name = problem_data.function_name.strip()
    if not function_name:
        raise ProblemServiceError(
            status_code=HTTPStatus.BAD_REQUEST.value,
            detail="function_name is required",
        )

    category = CategoryRepository(db).get(problem_data.category_id)
    if not category:
        raise ProblemServiceError(
            status_code=HTTPStatus.NOT_FOUND.value,
            detail="Category not found"
        )

    difficulty = DifficultyRepository(db).get(problem_data.difficulty_id)
    if not difficulty:
        raise ProblemServiceError(
            status_code=HTTPStatus.NOT_FOUND.value,
            detail="Difficulty not found"
        )

    existing_problem = problems.get_by_title(problem_data.title)
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
        function_name=function_name,
    )

    problems.add(new_problem)
    db.commit()
    db.refresh(new_problem)

    return get_problem_by_id(db, new_problem.id)


def solve_problem(db: Session, problem_id: int, user_id: int) -> UserSolvedProblem:
    problem = ProblemRepository(db).get(problem_id)
    if not problem:
        raise ProblemServiceError(
            status_code=HTTPStatus.NOT_FOUND.value,
            detail="Problem not found"
        )

    solved_problems = UserSolvedProblemRepository(db)
    existing_solution = solved_problems.get(user_id=user_id, problem_id=problem_id)

    if existing_solution:
        raise ProblemServiceError(
            status_code=HTTPStatus.BAD_REQUEST.value,
            detail="Problem already solved by this user"
        )

    new_solution = UserSolvedProblem(
        user_id=user_id,
        problem_id=problem_id,
    )

    solved_problems.add(new_solution)
    db.commit()
    db.refresh(new_solution)

    return new_solution


def get_user_solved_problems(db: Session, user_id: int) -> List[Problem]:
    return ProblemRepository(db).list_solved_by_user(user_id)


def get_problem_template(db: Session, problem_id: int, language_id: int) -> ProblemTemplate:
    template = ProblemTemplateRepository(db).get_for_problem_language(
        problem_id, language_id
    )
    if not template:
        raise ProblemServiceError(
            status_code=HTTPStatus.NOT_FOUND.value,
            detail="No template found for this problem/language combination",
        )
    return template
