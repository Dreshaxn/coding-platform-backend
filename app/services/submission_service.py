"""Submission service utilities for creating and retrieving submissions."""
from http import HTTPStatus
from typing import Optional, Tuple, List, Dict, Any

from sqlalchemy.orm import Session

from app.models import Language, Problem, Submission
from app.models.submission import SubmissionStatus
from app.schemas.submission import SubmissionCreate
from app.services.judge_queue import get_test_cases


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
) -> Tuple[Submission, List[Dict[str, Any]]]:
    """
    Create a new submission and return the submission and test cases.
    Raises SubmissionServiceError if the problem or language is not found.
    """
    problem = db.query(Problem).filter(Problem.id == data.problem_id).first()
    if not problem:
        raise SubmissionServiceError(
            status_code=HTTPStatus.NOT_FOUND.value, detail="Problem not found"
        )

    language = db.query(Language).filter(Language.id == data.language_id).first()
    if not language:
        raise SubmissionServiceError(
            status_code=HTTPStatus.NOT_FOUND.value, detail="Language not found"
        )
    if not language.is_active:
        raise SubmissionServiceError(
            status_code=HTTPStatus.BAD_REQUEST.value, detail="Language not supported"
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
    db.add(submission)
    db.commit()
    db.refresh(submission)

    return submission, test_cases


def get_submission(db: Session, submission_id: int, user_id: int) -> Submission:
    """
    Get a single submission by ID, scoped to the requesting user.
    Raises SubmissionServiceError if not found.
    """
    submission = (
        db.query(Submission)
        .filter(Submission.id == submission_id, Submission.user_id == user_id)
        .first()
    )
    if not submission:
        raise SubmissionServiceError(
            status_code=HTTPStatus.NOT_FOUND.value, detail="Submission not found"
        )
    return submission


def get_user_submissions(
    db: Session, user_id: int, limit: int = 20, offset: int = 0
) -> List[Submission]:
    """Get paginated submissions for a user, most recent first."""
    return (
        db.query(Submission)
        .filter(Submission.user_id == user_id)
        .order_by(Submission.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
