import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Callable, Any
from sqlalchemy.orm import Session

from app.models.submission import Submission, SubmissionStatus
from app.services.judge_queue import judgeSubmission


_executor = ThreadPoolExecutor(max_workers=4)


def judgeSync(db: Session, submission: Submission) -> Submission:
    return judgeSubmission(db, submission)


async def judgeAsync(db: Session, submission: Submission) -> Submission:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, judgeSubmission, db, submission)


def judgeBackground(db: Session, submissionId: int, onComplete: Optional[Callable[[Submission], Any]] = None) -> None:
    def task():
        submission = db.query(Submission).filter(Submission.id == submissionId).first()
        if submission:
            result = judgeSubmission(db, submission)
            if onComplete:
                onComplete(result)

    _executor.submit(task)


def getStatus(db: Session, submissionId: int) -> dict:
    submission = db.query(Submission).filter(Submission.id == submissionId).first()

    if not submission:
        return {"found": False, "error": "Submission not found"}

    return {
        "found": True,
        "id": submission.id,
        "status": submission.status.value,
        "is_complete": submission.status not in (SubmissionStatus.PENDING, SubmissionStatus.RUNNING),
        "passed": submission.passed,
        "passed_count": submission.passed_count,
        "total_count": submission.total_count,
        "results": submission.results
    }
