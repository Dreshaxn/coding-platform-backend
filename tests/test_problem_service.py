"""Unit tests for problem service."""
import pytest
from unittest.mock import Mock, MagicMock
from http import HTTPStatus
from datetime import datetime

from app.services.problem_service import (
    ProblemServiceError,
    get_problems,
    get_problem_by_id,
    create_problem,
    solve_problem,
    get_user_solved_problems,
)
from app.schemas.problem import ProblemCreate
from app.models.problem import Problem
from app.models.category import Category
from app.models.difficulty import Difficulty
from app.models.user_solved_problem import UserSolvedProblem


class TestGetProblems:
    """Tests for get_problems function."""

    def test_get_problems_success(self, mock_db, sample_problem):
        """Test successfully retrieving problems."""
        mock_query = MagicMock()
        mock_query.options.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [sample_problem]
        
        mock_db.query.return_value = mock_query
        
        result = get_problems(mock_db, skip=0, limit=10)
        
        assert len(result) == 1
        assert result[0].id == 1
        assert result[0].title == "Two Sum"
        mock_db.query.assert_called_once_with(Problem)

    def test_get_problems_empty(self, mock_db):
        """Test retrieving problems when none exist."""
        mock_query = MagicMock()
        mock_query.options.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        
        mock_db.query.return_value = mock_query
        
        result = get_problems(mock_db)
        
        assert len(result) == 0


class TestGetProblemById:
    """Tests for get_problem_by_id function."""

    def test_get_problem_by_id_success(self, mock_db, sample_problem):
        """Test successfully retrieving a problem by ID."""
        mock_query = MagicMock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = sample_problem
        
        mock_db.query.return_value = mock_query
        
        result = get_problem_by_id(mock_db, problem_id=1)
        
        assert result.id == 1
        assert result.title == "Two Sum"
        mock_db.query.assert_called_once_with(Problem)

    def test_get_problem_by_id_not_found(self, mock_db):
        """Test retrieving a problem that doesn't exist."""
        mock_query = MagicMock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        
        mock_db.query.return_value = mock_query
        
        with pytest.raises(ProblemServiceError) as exc_info:
            get_problem_by_id(mock_db, problem_id=999)
        
        assert exc_info.value.status_code == HTTPStatus.NOT_FOUND.value
        assert "Problem not found" in exc_info.value.detail


class TestCreateProblem:
    """Tests for create_problem function."""

    def test_create_problem_success(
        self, mock_db, sample_category, sample_difficulty, sample_problem
    ):
        """Test successfully creating a problem."""
        problem_data = ProblemCreate(
            title="New Problem",
            description="A new problem",
            difficulty_id=1,
            category_id=1
        )
        
        # Mock category query
        category_query = MagicMock()
        category_query.filter.return_value = category_query
        category_query.first.return_value = sample_category
        
        # Mock difficulty query
        difficulty_query = MagicMock()
        difficulty_query.filter.return_value = difficulty_query
        difficulty_query.first.return_value = sample_difficulty
        
        # Mock problem queries
        problem_query = MagicMock()
        problem_query.filter.return_value = problem_query
        problem_query.first.return_value = None  # No existing problem
        
        # Mock get_problem_by_id call
        get_problem_query = MagicMock()
        get_problem_query.options.return_value = get_problem_query
        get_problem_query.filter.return_value = get_problem_query
        get_problem_query.first.return_value = sample_problem
        
        def query_side_effect(model):
            if model == Category:
                return category_query
            elif model == Difficulty:
                return difficulty_query
            elif model == Problem:
                if mock_db.query.call_count <= 3:
                    return problem_query
                else:
                    return get_problem_query
        
        mock_db.query.side_effect = query_side_effect
        
        result = create_problem(mock_db, problem_data)
        
        assert result.id == 1
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_create_problem_category_not_found(self, mock_db):
        """Test creating a problem with non-existent category."""
        problem_data = ProblemCreate(
            title="New Problem",
            description="A new problem",
            difficulty_id=1,
            category_id=999
        )
        
        category_query = MagicMock()
        category_query.filter.return_value = category_query
        category_query.first.return_value = None
        
        mock_db.query.return_value = category_query
        
        with pytest.raises(ProblemServiceError) as exc_info:
            create_problem(mock_db, problem_data)
        
        assert exc_info.value.status_code == HTTPStatus.NOT_FOUND.value
        assert "Category not found" in exc_info.value.detail

    def test_create_problem_difficulty_not_found(self, mock_db, sample_category):
        """Test creating a problem with non-existent difficulty."""
        problem_data = ProblemCreate(
            title="New Problem",
            description="A new problem",
            difficulty_id=999,
            category_id=1
        )
        
        def query_side_effect(model):
            if model == Category:
                query = MagicMock()
                query.filter.return_value = query
                query.first.return_value = sample_category
                return query
            elif model == Difficulty:
                query = MagicMock()
                query.filter.return_value = query
                query.first.return_value = None
                return query
        
        mock_db.query.side_effect = query_side_effect
        
        with pytest.raises(ProblemServiceError) as exc_info:
            create_problem(mock_db, problem_data)
        
        assert exc_info.value.status_code == HTTPStatus.NOT_FOUND.value
        assert "Difficulty not found" in exc_info.value.detail

    def test_create_problem_duplicate_title(self, mock_db, sample_category, sample_difficulty):
        """Test creating a problem with duplicate title."""
        problem_data = ProblemCreate(
            title="Existing Problem",
            description="A problem",
            difficulty_id=1,
            category_id=1
        )
        
        existing_problem = Problem(id=1, title="Existing Problem")
        
        def query_side_effect(model):
            if model == Category:
                query = MagicMock()
                query.filter.return_value = query
                query.first.return_value = sample_category
                return query
            elif model == Difficulty:
                query = MagicMock()
                query.filter.return_value = query
                query.first.return_value = sample_difficulty
                return query
            elif model == Problem:
                query = MagicMock()
                query.filter.return_value = query
                query.first.return_value = existing_problem
                return query
        
        mock_db.query.side_effect = query_side_effect
        
        with pytest.raises(ProblemServiceError) as exc_info:
            create_problem(mock_db, problem_data)
        
        assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST.value
        assert "already exists" in exc_info.value.detail


class TestSolveProblem:
    """Tests for solve_problem function."""

    def test_solve_problem_success(self, mock_db, sample_problem):
        """Test successfully solving a problem."""
        # Mock problem query
        problem_query = MagicMock()
        problem_query.filter.return_value = problem_query
        problem_query.first.return_value = sample_problem
        
        # Mock solution query (no existing solution)
        solution_query = MagicMock()
        solution_query.filter.return_value = solution_query
        solution_query.first.return_value = None
        
        def query_side_effect(model):
            if model == Problem:
                return problem_query
            elif model == UserSolvedProblem:
                return solution_query
        
        mock_db.query.side_effect = query_side_effect
        
        result = solve_problem(mock_db, problem_id=1, user_id=1)
        
        assert result.user_id == 1
        assert result.problem_id == 1
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_solve_problem_not_found(self, mock_db):
        """Test solving a problem that doesn't exist."""
        problem_query = MagicMock()
        problem_query.filter.return_value = problem_query
        problem_query.first.return_value = None
        
        mock_db.query.return_value = problem_query
        
        with pytest.raises(ProblemServiceError) as exc_info:
            solve_problem(mock_db, problem_id=999, user_id=1)
        
        assert exc_info.value.status_code == HTTPStatus.NOT_FOUND.value
        assert "Problem not found" in exc_info.value.detail

    def test_solve_problem_already_solved(self, mock_db, sample_problem):
        """Test solving a problem that's already been solved."""
        existing_solution = UserSolvedProblem(
            id=1,
            user_id=1,
            problem_id=1,
            solved_at=datetime.now()
        )
        
        problem_query = MagicMock()
        problem_query.filter.return_value = problem_query
        problem_query.first.return_value = sample_problem
        
        solution_query = MagicMock()
        solution_query.filter.return_value = solution_query
        solution_query.first.return_value = existing_solution
        
        def query_side_effect(model):
            if model == Problem:
                return problem_query
            elif model == UserSolvedProblem:
                return solution_query
        
        mock_db.query.side_effect = query_side_effect
        
        with pytest.raises(ProblemServiceError) as exc_info:
            solve_problem(mock_db, problem_id=1, user_id=1)
        
        assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST.value
        assert "already solved" in exc_info.value.detail


class TestGetUserSolvedProblems:
    """Tests for get_user_solved_problems function."""

    def test_get_user_solved_problems_success(self, mock_db, sample_problem):
        """Test successfully retrieving user's solved problems."""
        mock_query = MagicMock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.options.return_value = mock_query
        mock_query.all.return_value = [sample_problem]
        
        mock_db.query.return_value = mock_query
        
        result = get_user_solved_problems(mock_db, user_id=1)
        
        assert len(result) == 1
        assert result[0].id == 1
        mock_db.query.assert_called_once_with(Problem)

    def test_get_user_solved_problems_empty(self, mock_db):
        """Test retrieving solved problems when user has none."""
        mock_query = MagicMock()
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.options.return_value = mock_query
        mock_query.all.return_value = []
        
        mock_db.query.return_value = mock_query
        
        result = get_user_solved_problems(mock_db, user_id=1)
        
        assert len(result) == 0

