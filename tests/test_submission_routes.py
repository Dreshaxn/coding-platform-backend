"""
Integration-ish tests for the submissions API.

Goal: verify that a user can submit code and the system:
1) persists the submission in the DB
2) enqueues it for async judging
3) returns/fetches submission state without depending on worker execution
"""

from __future__ import annotations

from typing import Generator

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import RedisError
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
from app.models.test_case import TestCase as ProblemCaseModel
from app.models.submission import Submission, SubmissionStatus


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

    # Older route versions used a module-level SessionLocal for background tasks.
    # Keep this conditional for compatibility across refactors.
    import app.api.routes.submissions as submissions_routes

    if hasattr(submissions_routes, "SessionLocal"):
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
        description="Return argument",
        difficulty_id=1,
        category_id=1,
        function_name="echo",
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
    tc1 = ProblemCaseModel(
        id=1,
        problem_id=1,
        input="\"hello\"",
        expected_output="\"hello\"",
        is_hidden=False,
        order=1,
    )
    tc2 = ProblemCaseModel(
        id=2,
        problem_id=1,
        input="\"secret\"",
        expected_output="\"secret\"",
        is_hidden=True,
        order=2,
    )

    db.add_all([category, difficulty, problem, language, tc1, tc2])
    db.commit()


class TestSubmissionEndpoint:
    def test_submit_persists_and_enqueues_pending_submission(
        self, client: TestClient, db: Session, monkeypatch
    ):
        _seed_problem_language_and_tests(db)

        import app.services.submission_service as submission_service

        queued_submission_ids: list[int] = []

        def _enqueue_mock(submission_id: int) -> None:
            queued_submission_ids.append(submission_id)

        monkeypatch.setattr(
            submission_service, "enqueue_submission", _enqueue_mock, raising=True
        )

        payload = {
            "problem_id": 1,
            "language_id": 1,
            "code": "class Solution:\n    def echo(self, value):\n        return value",
        }

        resp = client.post("/submissions", json=payload, headers={"Authorization": "Bearer mock"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["problem_id"] == 1
        assert body["language_id"] == 1
        assert body["user_id"] == 1
        assert body["status"] == SubmissionStatus.PENDING.value
        assert body["passed"] is False
        assert body["passed_count"] == 0
        assert body["total_count"] == 2
        assert body["results"] is None

        submission_id = body["id"]
        assert queued_submission_ids == [submission_id]

        stored = db.query(Submission).filter(Submission.id == submission_id).first()
        assert stored is not None
        assert stored.status == SubmissionStatus.PENDING

        resp2 = client.get(f"/submissions/{submission_id}", headers={"Authorization": "Bearer mock"})
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["status"] == SubmissionStatus.PENDING.value
        assert updated["passed"] is False

    def test_submit_does_not_judge_in_api_process(
        self, client: TestClient, db: Session, monkeypatch
    ):
        _seed_problem_language_and_tests(db)

        import app.services.submission_service as submission_service
        import app.services.judge_queue as judge_queue

        monkeypatch.setattr(
            submission_service, "enqueue_submission", lambda _submission_id: None, raising=True
        )

        def _run_code_should_not_be_called(*_args, **_kwargs):
            raise AssertionError("run_code should not be called in API request path")

        monkeypatch.setattr(
            judge_queue, "run_code", _run_code_should_not_be_called, raising=True
        )

        payload = {
            "problem_id": 1,
            "language_id": 1,
            "code": "class Solution:\n    def echo(self, value):\n        return 'nope'",
        }

        resp = client.post("/submissions", json=payload, headers={"Authorization": "Bearer mock"})
        assert resp.status_code == 201
        updated = resp.json()
        assert updated["status"] == SubmissionStatus.PENDING.value
        assert updated["passed"] is False
        assert updated["passed_count"] == 0
        assert updated["total_count"] == 2
        assert updated["results"] is None

    def test_submit_rejects_language_without_driver_support(self, client: TestClient, db: Session):
        # Seed a Java language entry (driver currently only supports Python)
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

        payload = {
            "problem_id": 1,
            "language_id": 2,
            "code": "class Solution { public Object echo(Object value) { return value; } }",
        }

        resp = client.post("/submissions", json=payload, headers={"Authorization": "Bearer mock"})
        assert resp.status_code == 400
        assert "driver-based execution" in resp.json()["detail"]

    def test_submit_returns_503_when_redis_enqueue_is_unavailable(
        self, client: TestClient, db: Session, monkeypatch
    ):
        _seed_problem_language_and_tests(db)

        import app.services.submission_service as submission_service

        monkeypatch.setattr(
            submission_service,
            "enqueue_submission",
            lambda _submission_id: (_ for _ in ()).throw(RedisError("redis down")),
            raising=True,
        )

        payload = {
            "problem_id": 1,
            "language_id": 1,
            "code": "class Solution:\n    def echo(self, value):\n        return value",
        }

        resp = client.post("/submissions", json=payload, headers={"Authorization": "Bearer mock"})
        assert resp.status_code == 503
        assert resp.json()["detail"] == "Submission queue unavailable"

        stored = db.query(Submission).first()
        assert stored is not None
        assert stored.status == SubmissionStatus.RUNTIME_ERROR
        assert stored.results == [{"error": "Submission queue unavailable"}]

    def test_submit_succeeds_when_redis_cache_read_write_fails(
        self, client: TestClient, db: Session, monkeypatch
    ):
        _seed_problem_language_and_tests(db)

        import app.services.submission_service as submission_service
        import app.services.judge_queue as judge_queue

        monkeypatch.setattr(
            submission_service, "enqueue_submission", lambda _submission_id: None, raising=True
        )
        monkeypatch.setattr(
            judge_queue,
            "cache_get_sync",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(RedisError("redis cache read down")),
            raising=True,
        )
        monkeypatch.setattr(
            judge_queue,
            "cache_set_sync",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(RedisError("redis cache write down")),
            raising=True,
        )

        payload = {
            "problem_id": 1,
            "language_id": 1,
            "code": "class Solution:\n    def echo(self, value):\n        return value",
        }

        resp = client.post("/submissions", json=payload, headers={"Authorization": "Bearer mock"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == SubmissionStatus.PENDING.value
        assert body["total_count"] == 2
