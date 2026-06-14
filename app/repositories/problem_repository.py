from typing import List, Optional

from sqlalchemy.orm import Session, joinedload

from app.models.category import Category
from app.models.difficulty import Difficulty
from app.models.problem import Problem
from app.models.problem_template import ProblemTemplate
from app.models.user_solved_problem import UserSolvedProblem


class ProblemRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self, skip: int = 0, limit: int = 100) -> List[Problem]:
        return (
            self.db.query(Problem)
            .options(
                joinedload(Problem.category),
                joinedload(Problem.difficulty),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get(self, problem_id: int) -> Optional[Problem]:
        return self.db.query(Problem).filter(Problem.id == problem_id).first()

    def get_with_details(self, problem_id: int) -> Optional[Problem]:
        return (
            self.db.query(Problem)
            .options(
                joinedload(Problem.category),
                joinedload(Problem.difficulty),
            )
            .filter(Problem.id == problem_id)
            .first()
        )

    def get_by_title(self, title: str) -> Optional[Problem]:
        return self.db.query(Problem).filter(Problem.title == title).first()

    def list_solved_by_user(self, user_id: int) -> List[Problem]:
        return (
            self.db.query(Problem)
            .join(UserSolvedProblem)
            .filter(UserSolvedProblem.user_id == user_id)
            .options(
                joinedload(Problem.category),
                joinedload(Problem.difficulty),
            )
            .all()
        )

    def select_for_race(
        self,
        *,
        problem_id: int | None = None,
        difficulty_id: int | None = None,
        category_id: int | None = None,
    ) -> Optional[Problem]:
        if problem_id is not None:
            return self.get(problem_id)

        query = self.db.query(Problem)
        if difficulty_id is not None:
            query = query.filter(Problem.difficulty_id == difficulty_id)
        if category_id is not None:
            query = query.filter(Problem.category_id == category_id)
        return query.order_by(Problem.id.asc()).first()

    def add(self, problem: Problem) -> None:
        self.db.add(problem)


class CategoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, category_id: int) -> Optional[Category]:
        return self.db.query(Category).filter(Category.id == category_id).first()


class DifficultyRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, difficulty_id: int) -> Optional[Difficulty]:
        return self.db.query(Difficulty).filter(Difficulty.id == difficulty_id).first()


class ProblemTemplateRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_for_problem_language(
        self, problem_id: int, language_id: int
    ) -> Optional[ProblemTemplate]:
        return (
            self.db.query(ProblemTemplate)
            .filter(
                ProblemTemplate.problem_id == problem_id,
                ProblemTemplate.language_id == language_id,
            )
            .first()
        )


class UserSolvedProblemRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, user_id: int, problem_id: int) -> Optional[UserSolvedProblem]:
        return (
            self.db.query(UserSolvedProblem)
            .filter(
                UserSolvedProblem.user_id == user_id,
                UserSolvedProblem.problem_id == problem_id,
            )
            .first()
        )

    def add(self, solved_problem: UserSolvedProblem) -> None:
        self.db.add(solved_problem)
