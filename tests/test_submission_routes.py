"""
Integration-ish tests for the submissions API.

Goal: verify that a user can submit code and the system:
1) persists the submission in the DB
2) runs judging in the background
3) stores pass/fail + per-test results

We stub the Docker executor (`run_code`) so tests don't require Docker.
"""

from __future__ import annotations

from typing import Generator, Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.main import app as fastapi_app
from app.api.deps import get_db, get_current_user
from app.db.base import Base

# Import models (registers them with SQLAlchemy metadata via app.models.__init__)
import app.models  # noqa: F401  # registers models; do not rename to `app` locally
from app.models.user import User
from app.models.category import Category
from app.models.difficulty import Difficulty
from app.models.problem import Problem
from app.models.language import Language
from app.models.test_case import TestCase as TestCaseModel
from app.models.submission import Submission, SubmissionStatus

from worker.config import ExecutionStatus
from worker.executor import ExecutionResult, TestResult as ExecutorTestResult


@pytest.fixture
def engine():
    """
    Shared in-memory SQLite database.

    StaticPool ensures all sessions share the same connection, which matters because
    our endpoint schedules a background task that creates a *new* session.
    """
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    return eng


@pytest.fixture
def TestingSessionLocal(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db(TestingSessionLocal) -> Generator[Session, None, None]:
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db: Session, TestingSessionLocal, monkeypatch) -> Generator[TestClient, None, None]:
    """
    TestClient with dependency overrides:
    - get_db uses the same session
    - get_current_user returns our seeded user
    Also patches `SessionLocal` used by the background task to use the test DB.
    """

    def _get_db_override():
        try:
            yield db
        finally:
            pass

    # Seed user (and keep it in DB so FK constraints won't bite us)
    user = User(
        id=1,
        email="test@example.com",
        username="testuser",
        hashed_password="hashed",
        is_active=True,
    )
    db.add(user)
    db.commit()

    fastapi_app.dependency_overrides[get_db] = _get_db_override
    fastapi_app.dependency_overrides[get_current_user] = lambda: user

    # Background judging uses a module-level SessionLocal imported in the route module.
    import app.api.routes.submissions as submissions_routes

    monkeypatch.setattr(submissions_routes, "SessionLocal", TestingSessionLocal, raising=True)

    with TestClient(fastapi_app) as c:
        yield c

    fastapi_app.dependency_overrides.clear()


def _seed_problem_language_and_tests(
    db: Session,
    *,
    language_id: int = 1,
    language_slug: str = "python3",
    language_name: str = "Python",
    language_version: str = "3.12",
    file_extension: str = ".py",
    compile_command: str | None = None,
    run_command: str = "python3 /app/solution.py",
) -> None:
    """Seed minimal data required for creating a submission."""
    category = Category(id=1, name="Arrays", description="Array problems")
    difficulty = Difficulty(id=1, name="easy", value=1)
    problem = Problem(
        id=1,
        title="Echo",
        description="Return input",
        difficulty_id=1,
        category_id=1,
    )
    language = Language(
        id=language_id,
        slug=language_slug,
        name=language_name,
        version=language_version,
        boilerplate_code="",
        file_extension=file_extension,
        compile_command=compile_command,
        run_command=run_command,
        is_active=True,
    )
    # One visible test, one hidden test
    tc1 = TestCaseModel(
        id=1,
        problem_id=1,
        input="hello\n",
        expected_output="hello",
        is_hidden=False,
        order=1,
    )
    tc2 = TestCaseModel(
        id=2,
        problem_id=1,
        input="secret\n",
        expected_output="secret",
        is_hidden=True,
        order=2,
    )

    db.add_all([category, difficulty, problem, language, tc1, tc2])
    db.commit()


def _stub_run_code_success(*args, **kwargs) -> ExecutionResult:
    """Fake executor output: all tests pass."""
    tests = [
        ExecutorTestResult(
            test_index=0,
            status=ExecutionStatus.SUCCESS,
            stdout="hello",
            stderr="",
            exit_code=0,
            runtime_ms=5.0,
            memory_kb=123.0,
        ),
        ExecutorTestResult(
            test_index=1,
            status=ExecutionStatus.SUCCESS,
            stdout="secret",
            stderr="",
            exit_code=0,
            runtime_ms=6.0,
            memory_kb=124.0,
        ),
    ]
    return ExecutionResult(
        status=ExecutionStatus.SUCCESS,
        test_results=tests,
        compilation_output=None,
        total_runtime_ms=15.0,
        passed_count=2,
        total_count=2,
    )


def _stub_run_code_wrong_answer(*args, **kwargs) -> ExecutionResult:
    """Fake executor output: first test fails, second passes."""
    tests = [
        ExecutorTestResult(
            test_index=0,
            status=ExecutionStatus.WRONG_ANSWER,
            stdout="nope",
            stderr="",
            exit_code=0,
            runtime_ms=5.0,
            memory_kb=123.0,
        ),
        ExecutorTestResult(
            test_index=1,
            status=ExecutionStatus.SUCCESS,
            stdout="secret",
            stderr="",
            exit_code=0,
            runtime_ms=6.0,
            memory_kb=124.0,
        ),
    ]
    return ExecutionResult(
        status=ExecutionStatus.WRONG_ANSWER,
        test_results=tests,
        compilation_output=None,
        total_runtime_ms=15.0,
        passed_count=1,
        total_count=2,
    )


class TestSubmissionEndpoint:
    def test_submit_persists_and_judges_in_background(self, client: TestClient, db: Session, monkeypatch):
        _seed_problem_language_and_tests(db)

        # Stub out Docker execution
        import app.services.judge_queue as judge_queue

        monkeypatch.setattr(judge_queue, "run_code", _stub_run_code_success, raising=True)

        payload = {
            "problem_id": 1,
            "language_id": 1,
            "code": "print(input())",
        }

        # Submit code. The API returns the created submission, and the background task
        # will judge it (using our stub) after the response is sent.
        resp = client.post("/submissions", json=payload, headers={"Authorization": "Bearer mock"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["problem_id"] == 1
        assert body["language_id"] == 1
        assert body["user_id"] == 1

        submission_id = body["id"]

        # Verify it was persisted
        stored = db.query(Submission).filter(Submission.id == submission_id).first()
        assert stored is not None

        # Fetch the submission again; by now the background task should have updated it.
        resp2 = client.get(f"/submissions/{submission_id}", headers={"Authorization": "Bearer mock"})
        assert resp2.status_code == 200
        updated = resp2.json()

        assert updated["status"] == SubmissionStatus.ACCEPTED.value
        assert updated["passed"] is True
        assert updated["passed_count"] == 2
        assert updated["total_count"] == 2

        # Results should exist for each test case
        results = updated["results"]
        assert isinstance(results, list)
        assert len(results) == 2

        # Visible test includes I/O details
        assert results[0]["is_hidden"] is False
        assert "input" in results[0]
        assert "expected_output" in results[0]
        assert "actual_output" in results[0]

        # Hidden test should not leak details
        assert results[1]["is_hidden"] is True
        assert "input" not in results[1]
        assert "expected_output" not in results[1]
        assert "actual_output" not in results[1]

    def test_submit_sets_wrong_answer_when_executor_reports_failure(self, client: TestClient, db: Session, monkeypatch):
        _seed_problem_language_and_tests(db)

        import app.services.judge_queue as judge_queue

        monkeypatch.setattr(judge_queue, "run_code", _stub_run_code_wrong_answer, raising=True)

        payload = {
            "problem_id": 1,
            "language_id": 1,
            "code": "print('nope')",
        }

        resp = client.post("/submissions", json=payload, headers={"Authorization": "Bearer mock"})
        assert resp.status_code == 201
        submission_id = resp.json()["id"]

        resp2 = client.get(f"/submissions/{submission_id}", headers={"Authorization": "Bearer mock"})
        assert resp2.status_code == 200
        updated = resp2.json()

        assert updated["status"] == SubmissionStatus.WRONG_ANSWER.value
        assert updated["passed"] is False
        assert updated["passed_count"] == 1
        assert updated["total_count"] == 2

    def test_submit_java_compilation_error_is_stored(self, client: TestClient, db: Session, monkeypatch):
        # Seed a Java language entry (different from Python)
        _seed_problem_language_and_tests(
            db,
            language_id=2,
            language_slug="java",
            language_name="Java",
            language_version="21",
            file_extension=".java",
            compile_command="javac -d /app /app/Solution.java",
            run_command="java -cp /app Solution",
        )

        # Stub executor to simulate a compilation failure
        def _stub_java_compile_error(*args, **kwargs) -> ExecutionResult:
            return ExecutionResult(
                status=ExecutionStatus.COMPILATION_ERROR,
                test_results=[],
                compilation_output="Solution.java:1: error: ';' expected",
                total_runtime_ms=10.0,
                passed_count=0,
                total_count=2,
            )

        import app.services.judge_queue as judge_queue

        monkeypatch.setattr(judge_queue, "run_code", _stub_java_compile_error, raising=True)

        payload = {
            "problem_id": 1,
            "language_id": 2,
            "code": "public class Solution { public static void main(String[] args) { System.out.println(\"hi\") } }",
        }

        resp = client.post("/submissions", json=payload, headers={"Authorization": "Bearer mock"})
        assert resp.status_code == 201
        submission_id = resp.json()["id"]

        # Should be updated by background judge with compilation error
        resp2 = client.get(f"/submissions/{submission_id}", headers={"Authorization": "Bearer mock"})
        assert resp2.status_code == 200
        updated = resp2.json()

        assert updated["status"] == SubmissionStatus.COMPILATION_ERROR.value
        assert updated["passed"] is False

        # Compilation errors are stored at the front of `results`
        assert isinstance(updated["results"], list)
        assert updated["results"][0].get("compilation_error")

