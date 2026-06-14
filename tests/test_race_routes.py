from __future__ import annotations

from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user, get_db
from app.db.base import Base
from app.main import app as fastapi_app

import app.models  # noqa: F401
from app.models.category import Category
from app.models.difficulty import Difficulty
from app.models.language import Language
from app.models.problem import Problem
from app.models.race import RaceParticipant, RaceParticipantStatus
from app.models.submission import Submission, SubmissionStatus
from app.models.test_case import TestCase as ProblemCaseModel
from app.models.user import User


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


@pytest.fixture
def users(db: Session) -> tuple[User, User]:
    user_one = User(
        id=1,
        email="dre@example.com",
        username="dre",
        hashed_password="hashed",
        is_active=True,
    )
    user_two = User(
        id=2,
        email="friend@example.com",
        username="friend",
        hashed_password="hashed",
        is_active=True,
    )
    db.add_all([user_one, user_two])
    db.commit()
    return user_one, user_two


@pytest.fixture
def auth_client(db: Session, users: tuple[User, User]) -> Generator[tuple[TestClient, dict], None, None]:
    auth_state = {"user": users[0]}

    def _get_db_override():
        try:
            yield db
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = _get_db_override
    fastapi_app.dependency_overrides[get_current_user] = lambda: auth_state["user"]

    with TestClient(fastapi_app) as client:
        yield client, auth_state

    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def race_seed(db: Session) -> None:
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
    test_case = ProblemCaseModel(
        id=1,
        problem_id=1,
        input='"hello"',
        expected_output='"hello"',
        is_hidden=False,
        order=1,
    )
    db.add_all([category, difficulty, problem, language, test_case])
    db.commit()


def test_race_create_join_ready_and_start(auth_client, race_seed):
    client, auth_state = auth_client

    create_resp = client.post(
        "/races",
        json={"name": "Friday Race", "problem_id": 1, "time_limit": 900},
    )
    assert create_resp.status_code == 201
    race = create_resp.json()
    assert race["name"] == "Friday Race"
    assert race["status"] == "waiting"
    assert race["problem_id"] == 1

    auth_state["user"] = auth_state["user"].__class__(
        id=2,
        email="friend@example.com",
        username="friend",
        hashed_password="hashed",
        is_active=True,
    )
    join_resp = client.post(f"/races/{race['id']}/join", json={"language_id": 1})
    assert join_resp.status_code == 200
    assert join_resp.json()["user_id"] == 2

    ready_two = client.post(f"/races/{race['id']}/ready")
    assert ready_two.status_code == 200
    assert ready_two.json()["status"] == "waiting"

    auth_state["user"] = auth_state["user"].__class__(
        id=1,
        email="dre@example.com",
        username="dre",
        hashed_password="hashed",
        is_active=True,
    )
    ready_one = client.post(f"/races/{race['id']}/ready")
    assert ready_one.status_code == 200
    assert ready_one.json()["status"] == "ready"

    start_resp = client.post(f"/races/{race['id']}/start")
    assert start_resp.status_code == 200
    assert start_resp.json()["status"] == "running"
    assert start_resp.json()["started_at"] is not None


def test_race_submit_syncs_winner_and_progress(auth_client, race_seed, db: Session, monkeypatch):
    client, auth_state = auth_client
    import app.services.race_service as race_service

    create_resp = client.post(
        "/races",
        json={"name": "Final Race", "problem_id": 1, "time_limit": 900},
    )
    race_id = create_resp.json()["id"]

    auth_state["user"] = db.query(User).filter(User.id == 2).first()
    client.post(f"/races/{race_id}/join", json={"language_id": 1})
    client.post(f"/races/{race_id}/ready")

    auth_state["user"] = db.query(User).filter(User.id == 1).first()
    client.post(f"/races/{race_id}/ready")
    client.post(f"/races/{race_id}/start")

    def _fake_create_and_queue_submission(db_session, user_id, data):
        submission = Submission(
            user_id=user_id,
            problem_id=data.problem_id,
            language_id=data.language_id,
            code=data.code,
            status=SubmissionStatus.PENDING,
            total_count=1,
        )
        db_session.add(submission)
        db_session.commit()
        db_session.refresh(submission)
        return submission

    monkeypatch.setattr(
        race_service,
        "create_and_queue_submission",
        _fake_create_and_queue_submission,
        raising=True,
    )

    submit_resp = client.post(
        f"/races/{race_id}/submissions",
        json={
            "code": "class Solution:\n    def echo(self, value):\n        return value",
            "language_id": 1,
        },
    )
    assert submit_resp.status_code == 200
    race_submission = submit_resp.json()
    assert race_submission["verdict"] == "pending"

    stored_submission = db.query(Submission).filter(Submission.id == race_submission["submission_id"]).first()
    stored_submission.status = SubmissionStatus.ACCEPTED
    stored_submission.passed = True
    stored_submission.passed_count = 1
    stored_submission.total_count = 1
    db.commit()

    sync_resp = client.post(
        f"/races/{race_id}/submissions/{race_submission['submission_id']}/sync"
    )
    assert sync_resp.status_code == 200
    body = sync_resp.json()
    assert body["status"] == "finished"
    assert body["winner_id"] == 1
    assert body["ended_at"] is not None

    progress_resp = client.get(f"/races/{race_id}/progress")
    assert progress_resp.status_code == 200
    progress = progress_resp.json()
    assert progress["participants"][0]["progress"] == 1
    assert progress["submissions"][0]["verdict"] == "accepted"


def test_race_progress_expires_running_race(auth_client, race_seed, db: Session):
    client, auth_state = auth_client

    create_resp = client.post(
        "/races",
        json={"name": "Fast Race", "problem_id": 1, "time_limit": 0},
    )
    race_id = create_resp.json()["id"]

    auth_state["user"] = db.query(User).filter(User.id == 2).first()
    client.post(f"/races/{race_id}/join", json={"language_id": 1})
    client.post(f"/races/{race_id}/ready")

    auth_state["user"] = db.query(User).filter(User.id == 1).first()
    client.post(f"/races/{race_id}/ready")
    start_resp = client.post(f"/races/{race_id}/start")
    assert start_resp.json()["status"] == "running"

    progress_resp = client.get(f"/races/{race_id}/progress")
    assert progress_resp.status_code == 200
    assert progress_resp.json()["race"]["status"] == "finished"
    assert progress_resp.json()["race"]["ended_at"] is not None


def test_forfeit_before_start_marks_participant_left_and_resets_ready(auth_client, race_seed, db: Session):
    client, auth_state = auth_client

    create_resp = client.post(
        "/races",
        json={"name": "Forfeit Ready Race", "problem_id": 1, "time_limit": 900},
    )
    race_id = create_resp.json()["id"]

    auth_state["user"] = db.query(User).filter(User.id == 2).first()
    client.post(f"/races/{race_id}/join", json={"language_id": 1})
    client.post(f"/races/{race_id}/ready")

    auth_state["user"] = db.query(User).filter(User.id == 1).first()
    ready_resp = client.post(f"/races/{race_id}/ready")
    assert ready_resp.json()["status"] == "ready"

    forfeit_resp = client.post(f"/races/{race_id}/forfeit")
    assert forfeit_resp.status_code == 200
    assert forfeit_resp.json()["status"] == "waiting"

    participant = (
        db.query(RaceParticipant)
        .filter(
            RaceParticipant.race_id == race_id,
            RaceParticipant.user_id == 1,
        )
        .first()
    )
    assert participant.final_status == RaceParticipantStatus.LEFT
    assert participant.is_ready is False


def test_forfeit_during_running_race_awards_remaining_participant(auth_client, race_seed, db: Session):
    client, auth_state = auth_client

    create_resp = client.post(
        "/races",
        json={"name": "Running Forfeit Race", "problem_id": 1, "time_limit": 900},
    )
    race_id = create_resp.json()["id"]

    auth_state["user"] = db.query(User).filter(User.id == 2).first()
    client.post(f"/races/{race_id}/join", json={"language_id": 1})
    client.post(f"/races/{race_id}/ready")

    auth_state["user"] = db.query(User).filter(User.id == 1).first()
    client.post(f"/races/{race_id}/ready")
    client.post(f"/races/{race_id}/start")

    auth_state["user"] = db.query(User).filter(User.id == 2).first()
    forfeit_resp = client.post(f"/races/{race_id}/forfeit")

    assert forfeit_resp.status_code == 200
    body = forfeit_resp.json()
    assert body["status"] == "finished"
    assert body["winner_id"] == 1
    assert body["ended_at"] is not None


def test_forfeit_after_race_finished_is_rejected(auth_client, race_seed, db: Session):
    client, auth_state = auth_client

    create_resp = client.post(
        "/races",
        json={"name": "Finished Forfeit Race", "problem_id": 1, "time_limit": 900},
    )
    race_id = create_resp.json()["id"]

    auth_state["user"] = db.query(User).filter(User.id == 2).first()
    client.post(f"/races/{race_id}/join", json={"language_id": 1})
    client.post(f"/races/{race_id}/ready")

    auth_state["user"] = db.query(User).filter(User.id == 1).first()
    client.post(f"/races/{race_id}/ready")
    client.post(f"/races/{race_id}/start")
    client.post(f"/races/{race_id}/forfeit")

    auth_state["user"] = db.query(User).filter(User.id == 2).first()
    second_forfeit_resp = client.post(f"/races/{race_id}/forfeit")

    assert second_forfeit_resp.status_code == 400
    assert second_forfeit_resp.json()["detail"] == "Race has already finished"


def test_non_participant_cannot_forfeit(auth_client, race_seed, db: Session):
    client, auth_state = auth_client

    third_user = User(
        id=3,
        email="stranger@example.com",
        username="stranger",
        hashed_password="hashed",
        is_active=True,
    )
    db.add(third_user)
    db.commit()

    create_resp = client.post(
        "/races",
        json={"name": "Private Race", "problem_id": 1, "time_limit": 900},
    )
    race_id = create_resp.json()["id"]

    auth_state["user"] = third_user
    forfeit_resp = client.post(f"/races/{race_id}/forfeit")

    assert forfeit_resp.status_code == 403
    assert forfeit_resp.json()["detail"] == "User is not participating in this race"


def test_non_creator_cannot_start_race(auth_client, race_seed, db: Session):
    client, auth_state = auth_client

    create_resp = client.post(
        "/races",
        json={"name": "Creator Only Race", "problem_id": 1, "time_limit": 900},
    )
    race_id = create_resp.json()["id"]

    auth_state["user"] = db.query(User).filter(User.id == 2).first()
    client.post(f"/races/{race_id}/join", json={"language_id": 1})
    client.post(f"/races/{race_id}/ready")

    auth_state["user"] = db.query(User).filter(User.id == 1).first()
    client.post(f"/races/{race_id}/ready")

    auth_state["user"] = db.query(User).filter(User.id == 2).first()
    start_resp = client.post(f"/races/{race_id}/start")

    assert start_resp.status_code == 403
    assert start_resp.json()["detail"] == "Only the race creator can start the race"


def test_start_race_twice_is_rejected(auth_client, race_seed, db: Session):
    client, auth_state = auth_client

    create_resp = client.post(
        "/races",
        json={"name": "Double Start Race", "problem_id": 1, "time_limit": 900},
    )
    race_id = create_resp.json()["id"]

    auth_state["user"] = db.query(User).filter(User.id == 2).first()
    client.post(f"/races/{race_id}/join", json={"language_id": 1})
    client.post(f"/races/{race_id}/ready")

    auth_state["user"] = db.query(User).filter(User.id == 1).first()
    client.post(f"/races/{race_id}/ready")

    first_start_resp = client.post(f"/races/{race_id}/start")
    second_start_resp = client.post(f"/races/{race_id}/start")

    assert first_start_resp.status_code == 200
    assert second_start_resp.status_code == 400
    assert second_start_resp.json()["detail"] == "Race is not ready to start"


def test_join_running_race_is_rejected(auth_client, race_seed, db: Session):
    client, auth_state = auth_client

    third_user = User(
        id=3,
        email="late@example.com",
        username="late",
        hashed_password="hashed",
        is_active=True,
    )
    db.add(third_user)
    db.commit()

    create_resp = client.post(
        "/races",
        json={"name": "No Late Join Race", "problem_id": 1, "time_limit": 900},
    )
    race_id = create_resp.json()["id"]

    auth_state["user"] = db.query(User).filter(User.id == 2).first()
    client.post(f"/races/{race_id}/join", json={"language_id": 1})
    client.post(f"/races/{race_id}/ready")

    auth_state["user"] = db.query(User).filter(User.id == 1).first()
    client.post(f"/races/{race_id}/ready")
    client.post(f"/races/{race_id}/start")

    auth_state["user"] = third_user
    join_resp = client.post(f"/races/{race_id}/join", json={"language_id": 1})

    assert join_resp.status_code == 400
    assert join_resp.json()["detail"] == "Race has already started"


def test_non_participant_cannot_submit_to_race(auth_client, race_seed, db: Session):
    client, auth_state = auth_client

    third_user = User(
        id=3,
        email="submitter@example.com",
        username="submitter",
        hashed_password="hashed",
        is_active=True,
    )
    db.add(third_user)
    db.commit()

    create_resp = client.post(
        "/races",
        json={"name": "Submit Permission Race", "problem_id": 1, "time_limit": 900},
    )
    race_id = create_resp.json()["id"]

    auth_state["user"] = db.query(User).filter(User.id == 2).first()
    client.post(f"/races/{race_id}/join", json={"language_id": 1})
    client.post(f"/races/{race_id}/ready")

    auth_state["user"] = db.query(User).filter(User.id == 1).first()
    client.post(f"/races/{race_id}/ready")
    client.post(f"/races/{race_id}/start")

    auth_state["user"] = third_user
    submit_resp = client.post(
        f"/races/{race_id}/submissions",
        json={
            "code": "class Solution:\n    def echo(self, value):\n        return value",
            "language_id": 1,
        },
    )

    assert submit_resp.status_code == 403
    assert submit_resp.json()["detail"] == "User is not participating in this race"


def test_change_language_during_running_race_is_rejected(auth_client, race_seed, db: Session):
    client, auth_state = auth_client

    second_language = Language(
        id=2,
        slug="python-alt",
        name="Python Alt",
        version="3.12",
        boilerplate_code="",
        file_extension=".py",
        compile_command=None,
        run_command="python3 /app/solution.py",
        is_active=True,
    )
    db.add(second_language)
    db.commit()

    create_resp = client.post(
        "/races",
        json={"name": "Language Lock Race", "problem_id": 1, "time_limit": 900},
    )
    race_id = create_resp.json()["id"]

    auth_state["user"] = db.query(User).filter(User.id == 2).first()
    client.post(f"/races/{race_id}/join", json={"language_id": 1})
    client.post(f"/races/{race_id}/ready")

    auth_state["user"] = db.query(User).filter(User.id == 1).first()
    client.post(f"/races/{race_id}/ready")
    client.post(f"/races/{race_id}/start")

    change_resp = client.post(f"/races/{race_id}/language/2")

    assert change_resp.status_code == 400
    assert change_resp.json()["detail"] == "Race has already started"
