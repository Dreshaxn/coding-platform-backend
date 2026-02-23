"""
Integration test for the DB-polling judge worker path.

This verifies that a pending submission is picked up by `JudgeWorker.run_once`,
judged through `judge_queue`, and persisted with final status/results.
"""

from __future__ import annotations

from typing import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base

# Ensure all models are registered on Base.metadata.
import app.models  # noqa: F401
from app.models.category import Category
from app.models.difficulty import Difficulty
from app.models.language import Language
from app.models.problem import Problem
from app.models.submission import Submission, SubmissionStatus
from app.models.test_case import TestCase
from app.models.user import User

from worker.config import ExecutionStatus
from worker.executor import ExecutionResult, TestResult as ExecutorTestResult
from worker.judge_worker import JudgeWorker


@pytest.fixture
def engine():
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


def _seed_pending_submission(db: Session) -> Submission:
    user = User(
        id=1,
        email="worker@example.com",
        username="workeruser",
        hashed_password="hashed",
        is_active=True,
    )
    category = Category(id=1, name="Arrays", description="Array problems")
    difficulty = Difficulty(id=1, name="easy", value=1)
    problem = Problem(
        id=1,
        title="Echo Worker",
        description="Echo input",
        difficulty_id=1,
        category_id=1,
    )
    language = Language(
        id=1,
        slug="python3",
        name="Python",
        version="3.12",
        boilerplate_code="",
        file_extension=".py",
        compile_command=None,
        run_command="python3 /app/solution.py",
        is_active=True,
    )
    tc1 = TestCase(
        id=1,
        problem_id=1,
        input="hello\n",
        expected_output="hello",
        is_hidden=False,
        order=1,
    )
    tc2 = TestCase(
        id=2,
        problem_id=1,
        input="secret\n",
        expected_output="secret",
        is_hidden=True,
        order=2,
    )
    submission = Submission(
        id=1,
        user_id=1,
        problem_id=1,
        language_id=1,
        code="print(input())",
        status=SubmissionStatus.PENDING,
        passed=False,
        passed_count=0,
        total_count=2,
    )

    db.add_all([user, category, difficulty, problem, language, tc1, tc2, submission])
    db.commit()
    db.refresh(submission)
    return submission


def _stub_run_code_success(*args, **kwargs) -> ExecutionResult:
    tests = [
        ExecutorTestResult(
            test_index=0,
            status=ExecutionStatus.SUCCESS,
            stdout="hello",
            stderr="",
            exit_code=0,
            runtime_ms=5.0,
            memory_kb=100.0,
        ),
        ExecutorTestResult(
            test_index=1,
            status=ExecutionStatus.SUCCESS,
            stdout="secret",
            stderr="",
            exit_code=0,
            runtime_ms=6.0,
            memory_kb=110.0,
        ),
    ]
    return ExecutionResult(
        status=ExecutionStatus.SUCCESS,
        test_results=tests,
        compilation_output=None,
        total_runtime_ms=20.0,
        passed_count=2,
        total_count=2,
    )


def test_judge_worker_processes_pending_submission(
    db: Session, TestingSessionLocal, monkeypatch
):
    _seed_pending_submission(db)

    import app.services.judge_queue as judge_queue
    import worker.judge_worker as judge_worker_module

    monkeypatch.setattr(judge_queue, "run_code", _stub_run_code_success, raising=True)
    monkeypatch.setattr(
        judge_worker_module, "SessionLocal", TestingSessionLocal, raising=True
    )

    worker = JudgeWorker(batch_size=5, worker_id="test-worker")
    processed = worker.run_once()
    assert processed == 1

    refreshed = db.query(Submission).filter(Submission.id == 1).first()
    assert refreshed is not None
    assert refreshed.status == SubmissionStatus.ACCEPTED
    assert refreshed.passed is True
    assert refreshed.passed_count == 2
    assert refreshed.total_count == 2
    assert isinstance(refreshed.results, list)
    assert len(refreshed.results) == 2

    # Visible test case details are present, hidden details are not leaked.
    assert refreshed.results[0]["is_hidden"] is False
    assert "input" in refreshed.results[0]
    assert refreshed.results[1]["is_hidden"] is True
    assert "input" not in refreshed.results[1]
