"""Pytest configuration and shared fixtures."""
import pytest
from unittest.mock import Mock, MagicMock
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.user import User
from app.models.problem import Problem
from app.models.category import Category
from app.models.difficulty import Difficulty
from app.models.user_solved_problem import UserSolvedProblem


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def sample_category():
    """Create a sample category."""
    return Category(
        id=1,
        name="Arrays",
        description="Array manipulation problems"
    )


@pytest.fixture
def sample_difficulty():
    """Create a sample difficulty."""
    return Difficulty(
        id=1,
        name="easy",
        value=1
    )


@pytest.fixture
def sample_problem(sample_category, sample_difficulty):
    """Create a sample problem."""
    problem = Problem(
        id=1,
        title="Two Sum",
        description="Find two numbers that add up to target",
        difficulty_id=1,
        category_id=1,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    problem.category = sample_category
    problem.difficulty = sample_difficulty
    return problem


@pytest.fixture
def sample_user():
    """Create a sample user."""
    return User(
        id=1,
        email="test@example.com",
        username="testuser",
        hashed_password="hashed",
        is_active=True
    )


@pytest.fixture
def sample_user_solved_problem(sample_user, sample_problem):
    """Create a sample user solved problem."""
    return UserSolvedProblem(
        id=1,
        user_id=1,
        problem_id=1,
        solved_at=datetime.now()
    )

