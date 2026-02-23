from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.submission import SubmissionCreate, SubmissionResponse
from app.cache.redis import enqueue_submission
from app.services.submission_service import (
    SubmissionServiceError,
    create_submission,
    get_submission as get_submission_service,
    get_user_submissions as get_user_submissions_service,
)

router = APIRouter()


@router.post("/submissions", response_model=SubmissionResponse, status_code=status.HTTP_201_CREATED)
def submit_code(
    submission_data: SubmissionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        submission, _ = create_submission(db, current_user.id, submission_data)
        # push onto redis queue — the judge worker picks it up via BRPOP
        enqueue_submission(submission.id)
        return submission
    except SubmissionServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
            headers=exc.headers,
        )


@router.get("/submissions/{submission_id}", response_model=SubmissionResponse)
def get_submission(
    submission_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return get_submission_service(db, submission_id, current_user.id)
    except SubmissionServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
            headers=exc.headers,
        )


@router.get("/submissions", response_model=List[SubmissionResponse])
def get_user_submissions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 20,
    offset: int = 0,
):
    return get_user_submissions_service(db, current_user.id, limit=limit, offset=offset)
