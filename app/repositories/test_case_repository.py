from typing import List

from sqlalchemy.orm import Session

from app.models.test_case import TestCase


class TestCaseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_problem(self, problem_id: int) -> List[TestCase]:
        return (
            self.db.query(TestCase)
            .filter(TestCase.problem_id == problem_id)
            .order_by(TestCase.order)
            .all()
        )
