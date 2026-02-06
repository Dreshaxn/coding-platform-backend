from http import HTTPStatus
from typing import Optional, Tuple, List, Dict, Any

from sqlalchemy.orm import Session

from app.models import Language, Problem, Submission
from app.models.submission import SubmissionStatus
from app.schemas.submission import SubmissionCreate
from app.services.judge_queue import getCachedTestCases, judgeSubmission


class SubmissionServiceError(Exception):
    def __init__(self, *, statusCode: int, detail: str, headers: Optional[dict] = None):
        self.statusCode = statusCode
        self.detail = detail
        self.headers = headers
        super().__init__(detail)


def createSubmission(db: Session, userId: int, data: SubmissionCreate) -> Tuple[Submission, List[Dict[str, Any]]]:
    problem = db.query(Problem).filter(Problem.id == data.problem_id).first()
    if not problem:
        raise SubmissionServiceError(statusCode=HTTPStatus.NOT_FOUND.value, detail="Problem not found")

    language = db.query(Language).filter(Language.id == data.language_id).first()
    if not language:
        raise SubmissionServiceError(statusCode=HTTPStatus.NOT_FOUND.value, detail="Language not found")
    if not language.is_active:
        raise SubmissionServiceError(statusCode=HTTPStatus.BAD_REQUEST.value, detail="Language not supported")

    testCases = getCachedTestCases(db, data.problem_id)

    submission = Submission(
        user_id=userId,
        problem_id=data.problem_id,
        language_id=data.language_id,
        code=data.code,
        status=SubmissionStatus.PENDING,
        total_count=len(testCases),
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    return submission, testCases


def createAndJudge(db: Session, userId: int, data: SubmissionCreate) -> Submission:
    submission, testCases = createSubmission(db, userId, data)
    return judgeSubmission(db, submission, testCases=testCases)
