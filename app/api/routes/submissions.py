from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.submission import Submission
from app.db.session import SessionLocal
from app.schemas.submission import SubmissionCreate, SubmissionResponse
from app.services.judge_queue import judgeSubmission
from app.services.submission_service import SubmissionServiceError, createSubmission

router = APIRouter()


def judgeInBackground(submissionId: int):
    db = SessionLocal()
    try:
        submission = db.query(Submission).filter(Submission.id == submissionId).first()
        if submission:
            judgeSubmission(db, submission)
    finally:
        db.close()


@router.post("/submissions", response_model=SubmissionResponse, status_code=status.HTTP_201_CREATED)
def submitCode(
    submissionData: SubmissionCreate,
    backgroundTasks: BackgroundTasks,
    currentUser: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        submission, _ = createSubmission(db, currentUser.id, submissionData)
        backgroundTasks.add_task(judgeInBackground, submission.id)
        return submission
    except SubmissionServiceError as e:
        raise HTTPException(status_code=e.statusCode, detail=e.detail)


@router.get("/submissions/{submissionId}", response_model=SubmissionResponse)
def getSubmission(
    submissionId: int,
    currentUser: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    submission = db.query(Submission).filter(
        Submission.id == submissionId,
        Submission.user_id == currentUser.id
    ).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    return submission


@router.get("/submissions", response_model=List[SubmissionResponse])
def getUserSubmissions(
    currentUser: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 20,
    offset: int = 0
):
    submissions = db.query(Submission).filter(
        Submission.user_id == currentUser.id
    ).order_by(Submission.created_at.desc()).offset(offset).limit(limit).all()
    return submissions
