"""Submission service utilities for creating and retrieving submissions."""
from http import HTTPStatus
from typing import Optional, List

from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from app.cache.redis import enqueue_submission
from app.models import Submission
from app.models.submission import SubmissionStatus
from app.repositories.language_repository import LanguageRepository
from app.repositories.problem_repository import ProblemRepository
from app.repositories.submission_repository import SubmissionRepository
from app.schemas.submission import SubmissionCreate
from app.services.judge_queue import get_test_cases
from worker.drivers import generate_driver


class SubmissionServiceError(Exception):
    """Domain-level error that can be translated into an HTTP exception."""

    def __init__(
        self, *, status_code: int, detail: str, headers: Optional[dict] = None
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.headers = headers
        super().__init__(detail)


def create_submission(
    db: Session, user_id: int, data: SubmissionCreate
) -> Submission:
    """
    Create and persist a new pending submission.
    Raises SubmissionServiceError if the problem or language is not found.
    """
    problem = ProblemRepository(db).get(data.problem_id)
    if not problem:
        raise SubmissionServiceError(
            status_code=HTTPStatus.NOT_FOUND.value, detail="Problem not found"
        )
    if not problem.function_name:
        raise SubmissionServiceError(
            status_code=HTTPStatus.BAD_REQUEST.value,
            detail="Problem is missing function_name for driver-based execution",
        )

    language = LanguageRepository(db).get(data.language_id)
    if not language:
        raise SubmissionServiceError(
            status_code=HTTPStatus.NOT_FOUND.value, detail="Language not found"
        )
    if not language.is_active:
        raise SubmissionServiceError(
            status_code=HTTPStatus.BAD_REQUEST.value, detail="Language not supported"
        )
    if not generate_driver(language.slug, problem.function_name):
        raise SubmissionServiceError(
            status_code=HTTPStatus.BAD_REQUEST.value,
            detail=f"Language '{language.slug}' does not support driver-based execution",
        )

    test_cases = get_test_cases(db, data.problem_id)

    submission = Submission(
        user_id=user_id,
        problem_id=data.problem_id,
        language_id=data.language_id,
        code=data.code,
        status=SubmissionStatus.PENDING,
        total_count=len(test_cases),
    )
    SubmissionRepository(db).add(submission)
    db.commit()
    db.refresh(submission)

    return submission


def create_and_queue_submission(
    db: Session, user_id: int, data: SubmissionCreate
) -> Submission:
    """
    Create a submission and enqueue it for async judging.
    Raises SubmissionServiceError when queueing is unavailable.
    """
    submission = create_submission(db, user_id, data)

    try:
        enqueue_submission(submission.id)
    except RedisError as exc:
        submission.status = SubmissionStatus.RUNTIME_ERROR
        submission.results = [{"error": "Submission queue unavailable"}]
        db.commit()
        db.refresh(submission)
        raise SubmissionServiceError(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE.value,
            detail="Submission queue unavailable",
        ) from exc

    return submission


def get_submission(db: Session, submission_id: int, user_id: int) -> Submission:
    """
    Get a single submission by ID, scoped to the requesting user.
    Raises SubmissionServiceError if not found.
    """
    submission = SubmissionRepository(db).get_for_user(submission_id, user_id)
    if not submission:
        raise SubmissionServiceError(
            status_code=HTTPStatus.NOT_FOUND.value, detail="Submission not found"
        )
    return submission


def get_user_submissions(
    db: Session, user_id: int, limit: int = 20, offset: int = 0
) -> List[Submission]:
    """Get paginated submissions for a user, most recent first."""
    return SubmissionRepository(db).list_for_user(user_id, limit=limit, offset=offset)
