"""Unit tests for problem routes."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import status
from datetime import datetime

from app.main import app
from app.api.deps import get_current_user
from app.services.problem_service import ProblemServiceError
from app.models.user import User
from app.models.problem import Problem
from app.models.category import Category
from app.models.difficulty import Difficulty
from app.models.user_solved_problem import UserSolvedProblem


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def sample_user():
    """Create a sample user for authentication."""
    return User(
        id=1,
        email="test@example.com",
        username="testuser",
        hashed_password="hashed",
        is_active=True
    )


@pytest.fixture
def auth_headers(sample_user):
    """Create authentication headers."""
    # Mock token that will be decoded to user_id=1
    return {"Authorization": "Bearer mock_token"}


class TestGetProblems:
    """Tests for GET /problems endpoint."""

    @patch("app.api.routes.problem.get_problems_service")
    def test_get_problems_success(self, mock_get_problems, client, sample_problem):
        """Test successfully retrieving problems."""
        mock_get_problems.return_value = [sample_problem]
        
        response = client.get("/problems")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == 1
        assert data[0]["title"] == "Two Sum"

    @patch("app.api.routes.problem.get_problems_service")
    def test_get_problems_empty(self, mock_get_problems, client):
        """Test retrieving problems when none exist."""
        mock_get_problems.return_value = []
        
        response = client.get("/problems")
        
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    @patch("app.api.routes.problem.get_problems_service")
    def test_get_problems_pagination(self, mock_get_problems, client):
        """Test pagination parameters."""
        mock_get_problems.return_value = []
        
        response = client.get("/problems?skip=10&limit=20")
        
        assert response.status_code == status.HTTP_200_OK
        mock_get_problems.assert_called_once()
        # Verify pagination was passed
        call_args = mock_get_problems.call_args
        assert call_args[1]["skip"] == 10
        assert call_args[1]["limit"] == 20


class TestGetProblem:
    """Tests for GET /problems/{problem_id} endpoint."""

    @patch("app.api.routes.problem.get_problem_by_id")
    def test_get_problem_success(self, mock_get_problem, client, sample_problem):
        """Test successfully retrieving a problem."""
        mock_get_problem.return_value = sample_problem
        
        response = client.get("/problems/1")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == 1
        assert data["title"] == "Two Sum"

    @patch("app.api.routes.problem.get_problem_by_id")
    def test_get_problem_not_found(self, mock_get_problem, client):
        """Test retrieving a problem that doesn't exist."""
        mock_get_problem.side_effect = ProblemServiceError(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Problem not found"
        )
        
        response = client.get("/problems/999")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Problem not found" in response.json()["detail"]


class TestCreateProblem:
    """Tests for POST /problems endpoint."""

    @patch("app.api.routes.problem.create_problem_service")
    def test_create_problem_success(self, mock_create_problem, client, sample_problem):
        """Test successfully creating a problem."""
        mock_create_problem.return_value = sample_problem
        
        problem_data = {
            "title": "New Problem",
            "description": "A new problem",
            "difficulty_id": 1,
            "category_id": 1
        }
        
        response = client.post("/problems", json=problem_data)
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["id"] == 1
        assert data["title"] == "Two Sum"

    @patch("app.api.routes.problem.create_problem_service")
    def test_create_problem_validation_error(self, mock_create_problem, client):
        """Test creating a problem with invalid data."""
        mock_create_problem.side_effect = ProblemServiceError(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Problem with this title already exists"
        )
        
        problem_data = {
            "title": "Existing Problem",
            "description": "A problem",
            "difficulty_id": 1,
            "category_id": 1
        }
        
        response = client.post("/problems", json=problem_data)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already exists" in response.json()["detail"]

    @patch("app.api.routes.problem.create_problem_service")
    def test_create_problem_category_not_found(self, mock_create_problem, client):
        """Test creating a problem with non-existent category."""
        mock_create_problem.side_effect = ProblemServiceError(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
        
        problem_data = {
            "title": "New Problem",
            "description": "A problem",
            "difficulty_id": 1,
            "category_id": 999
        }
        
        response = client.post("/problems", json=problem_data)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Category not found" in response.json()["detail"]


class TestSolveProblem:
    """Tests for POST /problems/{problem_id}/solve endpoint."""

    def test_solve_problem_success(self, client, sample_user):
        """Test successfully solving a problem."""
        solved_problem = UserSolvedProblem(
            id=1,
            user_id=1,
            problem_id=1,
            solved_at=datetime.now()
        )
        
        # Override the dependency
        app.dependency_overrides[get_current_user] = lambda: sample_user
        
        with patch("app.api.routes.problem.solve_problem_service") as mock_solve:
            mock_solve.return_value = solved_problem
            
            response = client.post(
                "/problems/1/solve",
                headers={"Authorization": "Bearer mock_token"}
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["user_id"] == 1
            assert data["problem_id"] == 1
        
        app.dependency_overrides.clear()

    def test_solve_problem_already_solved(self, client, sample_user):
        """Test solving a problem that's already been solved."""
        app.dependency_overrides[get_current_user] = lambda: sample_user
        
        with patch("app.api.routes.problem.solve_problem_service") as mock_solve:
            mock_solve.side_effect = ProblemServiceError(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Problem already solved by this user"
            )
            
            response = client.post(
                "/problems/1/solve",
                headers={"Authorization": "Bearer mock_token"}
            )
            
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "already solved" in response.json()["detail"]
        
        app.dependency_overrides.clear()

    def test_solve_problem_unauthorized(self, client):
        """Test solving a problem without authentication."""
        response = client.post("/problems/1/solve")
        
        # FastAPI returns 403 for missing auth
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED]


class TestGetMySolvedProblems:
    """Tests for GET /problems/solved/me endpoint."""

    def test_get_my_solved_problems_success(self, client, sample_user, sample_problem):
        """Test successfully retrieving user's solved problems."""
        app.dependency_overrides[get_current_user] = lambda: sample_user
        
        with patch("app.api.routes.problem.get_user_solved_problems") as mock_get_solved:
            mock_get_solved.return_value = [sample_problem]
            
            response = client.get(
                "/problems/solved/me",
                headers={"Authorization": "Bearer mock_token"}
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data) == 1
            assert data[0]["id"] == 1
        
        app.dependency_overrides.clear()

    def test_get_my_solved_problems_empty(self, client, sample_user):
        """Test retrieving solved problems when user has none."""
        app.dependency_overrides[get_current_user] = lambda: sample_user
        
        with patch("app.api.routes.problem.get_user_solved_problems") as mock_get_solved:
            mock_get_solved.return_value = []
            
            response = client.get(
                "/problems/solved/me",
                headers={"Authorization": "Bearer mock_token"}
            )
            
            assert response.status_code == status.HTTP_200_OK
            assert response.json() == []
        
        app.dependency_overrides.clear()

    def test_get_my_solved_problems_unauthorized(self, client):
        """Test retrieving solved problems without authentication."""
        response = client.get("/problems/solved/me")
        
        # FastAPI returns 403 for missing auth
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED]

