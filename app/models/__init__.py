# Import all models here so Alembic can detect them
# This file is imported by alembic/env.py to ensure all models are registered

from app.models.user import User  # noqa: F401
from app.models.user_stats import UserStats  # noqa: F401
from app.models.category import Category  # noqa: F401
from app.models.difficulty import Difficulty  # noqa: F401
from app.models.problem import Problem  # noqa: F401
from app.models.problem_template import ProblemTemplate  # noqa: F401
from app.models.test_case import TestCase  # noqa: F401
from app.models.language import Language  # noqa: F401
from app.models.submission import Submission, SubmissionStatus  # noqa: F401
from app.models.user_solved_problem import UserSolvedProblem  # noqa: F401

__all__ = [
    "User",
    "UserStats",
    "Category",
    "Difficulty",
    "Problem",
    "ProblemTemplate",
    "TestCase",
    "Language",
    "Submission",
    "SubmissionStatus",
    "UserSolvedProblem",
]
