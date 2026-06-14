from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.submission import Submission


class SubmissionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, submission_id: int) -> Optional[Submission]:
        return (
            self.db.query(Submission)
            .filter(Submission.id == submission_id)
            .first()
        )

    def get_for_user(self, submission_id: int, user_id: int) -> Optional[Submission]:
        return (
            self.db.query(Submission)
            .filter(Submission.id == submission_id, Submission.user_id == user_id)
            .first()
        )

    def list_for_user(
        self, user_id: int, limit: int = 20, offset: int = 0
    ) -> List[Submission]:
        return (
            self.db.query(Submission)
            .filter(Submission.user_id == user_id)
            .order_by(Submission.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def add(self, submission: Submission) -> None:
        self.db.add(submission)
