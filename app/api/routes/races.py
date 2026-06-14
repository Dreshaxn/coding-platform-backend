from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.race import (
    RaceCreate,
    RaceParticipantCreate,
    RaceParticipantResponse,
    RaceProgressResponse,
    RaceResponse,
    RaceSubmissionCreate,
    RaceSubmissionResponse,
)
from app.services.race_service import (
    RaceServiceError,
    change_language as change_language_service,
    create_race as create_race_service,
    forfeit_race as forfeit_race_service,
    get_race as get_race_service,
    get_race_progress as get_race_progress_service,
    join_race as join_race_service,
    set_ready as set_ready_service,
    start_race as start_race_service,
    submit_race_solution as submit_race_solution_service,
    sync_race_submission as sync_race_submission_service,
)

router = APIRouter()


def _raise_http(exc: RaceServiceError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail=exc.detail,
        headers=exc.headers,
    )


@router.post("/races", response_model=RaceResponse, status_code=status.HTTP_201_CREATED)
def create_race(
    race_data: RaceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return create_race_service(db, current_user.id, race_data)
    except RaceServiceError as exc:
        _raise_http(exc)


@router.get("/races/{race_id}", response_model=RaceResponse)
def get_race(
    race_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return get_race_service(db, race_id, current_user.id)
    except RaceServiceError as exc:
        _raise_http(exc)


@router.get("/races/{race_id}/progress", response_model=RaceProgressResponse)
def get_race_progress(
    race_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        race, participants, submissions = get_race_progress_service(
            db, race_id, current_user.id
        )
        return {
            "race": race,
            "participants": participants,
            "submissions": submissions,
        }
    except RaceServiceError as exc:
        _raise_http(exc)


@router.post("/races/{race_id}/join", response_model=RaceParticipantResponse)
def join_race(
    race_id: int,
    participant_data: RaceParticipantCreate = RaceParticipantCreate(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return join_race_service(db, race_id, current_user.id, participant_data)
    except RaceServiceError as exc:
        _raise_http(exc)


@router.post("/races/{race_id}/ready", response_model=RaceResponse)
def ready_up(
    race_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return set_ready_service(db, race_id, current_user.id, is_ready=True)
    except RaceServiceError as exc:
        _raise_http(exc)


@router.post("/races/{race_id}/unready", response_model=RaceResponse)
def unready(
    race_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return set_ready_service(db, race_id, current_user.id, is_ready=False)
    except RaceServiceError as exc:
        _raise_http(exc)


@router.post("/races/{race_id}/start", response_model=RaceResponse)
def start_race(
    race_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return start_race_service(db, race_id, current_user.id)
    except RaceServiceError as exc:
        _raise_http(exc)


@router.post("/races/{race_id}/language/{language_id}", response_model=RaceParticipantResponse)
def change_language(
    race_id: int,
    language_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return change_language_service(db, race_id, current_user.id, language_id)
    except RaceServiceError as exc:
        _raise_http(exc)


@router.post("/races/{race_id}/submissions", response_model=RaceSubmissionResponse)
def submit_race_solution(
    race_id: int,
    submission_data: RaceSubmissionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return submit_race_solution_service(db, race_id, current_user.id, submission_data)
    except RaceServiceError as exc:
        _raise_http(exc)


@router.post("/races/{race_id}/submissions/{submission_id}/sync", response_model=RaceResponse)
def sync_race_submission(
    race_id: int,
    submission_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return sync_race_submission_service(db, race_id, current_user.id, submission_id)
    except RaceServiceError as exc:
        _raise_http(exc)


@router.post("/races/{race_id}/forfeit", response_model=RaceResponse)
def forfeit_race(
    race_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return forfeit_race_service(db, race_id, current_user.id)
    except RaceServiceError as exc:
        _raise_http(exc)
