from http import HTTPStatus
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Language, Problem
from app.models.race import (
    Race,
    RaceParticipant,
    RaceParticipantStatus,
    RaceStatus,
    RaceSubmission,
)
from app.models.submission import SubmissionStatus
from app.repositories.language_repository import LanguageRepository
from app.repositories.problem_repository import ProblemRepository
from app.repositories.race_repository import (
    RaceParticipantRepository,
    RaceRepository,
    RaceSubmissionRepository,
)
from app.repositories.submission_repository import SubmissionRepository
from app.schemas.race import RaceCreate, RaceParticipantCreate, RaceSubmissionCreate
from app.schemas.submission import SubmissionCreate
from app.services.submission_service import (
    SubmissionServiceError,
    create_and_queue_submission,
)
from app.utils.datetime import utcnow_naive


TERMINAL_VERDICTS = {
    SubmissionStatus.ACCEPTED.value,
    SubmissionStatus.WRONG_ANSWER.value,
    SubmissionStatus.TIME_LIMIT_EXCEEDED.value,
    SubmissionStatus.MEMORY_LIMIT_EXCEEDED.value,
    SubmissionStatus.RUNTIME_ERROR.value,
    SubmissionStatus.COMPILATION_ERROR.value,
}


class RaceServiceError(Exception):
    def __init__(
        self, *, status_code: int, detail: str, headers: Optional[dict] = None
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.headers = headers
        super().__init__(detail)


def _raise_not_found(detail: str) -> None:
    raise RaceServiceError(status_code=HTTPStatus.NOT_FOUND.value, detail=detail)


def _get_race(db: Session, race_id: int) -> Race:
    race = RaceRepository(db).get(race_id)
    if not race:
        _raise_not_found("Race not found")
    return race


def _get_participant(db: Session, race_id: int, user_id: int) -> RaceParticipant:
    participant = RaceParticipantRepository(db).get(race_id, user_id)
    if not participant:
        raise RaceServiceError(
            status_code=HTTPStatus.FORBIDDEN.value,
            detail="User is not participating in this race",
        )
    return participant


def _select_problem(db: Session, race_data: RaceCreate) -> Problem:
    problem = ProblemRepository(db).select_for_race(
        problem_id=race_data.problem_id,
        difficulty_id=race_data.difficulty_id,
        category_id=race_data.category_id,
    )
    if not problem:
        if race_data.problem_id is not None:
            _raise_not_found("Problem not found")
        _raise_not_found("No matching problem found")
    return problem


def _select_language(db: Session, language_id: int | None) -> Language:
    language = LanguageRepository(db).get_active_or_default(language_id)
    if not language:
        _raise_not_found("Language not found")
    return language


def _pick_winner_by_progress(participants: list[RaceParticipant]) -> int | None:
    if not participants:
        return None
    best_progress = max(p.progress for p in participants)
    leaders = [p for p in participants if p.progress == best_progress]
    if len(leaders) == 1 and best_progress > 0:
        return leaders[0].user_id
    return None


def _apply_race_end_conditions(db: Session, race: Race) -> Race:
    if race.status != RaceStatus.RUNNING:
        return race

    participants = RaceParticipantRepository(db).list_for_race(race.id)
    submissions = RaceSubmissionRepository(db).list_for_race(race.id)

    accepted = next((s for s in submissions if s.verdict == SubmissionStatus.ACCEPTED.value), None)
    if accepted:
        race.status = RaceStatus.FINISHED
        race.winner_id = accepted.participant.user_id
        race.ended_at = utcnow_naive()
        return race

    if race.started_at and (utcnow_naive() - race.started_at).total_seconds() >= race.time_limit:
        race.status = RaceStatus.FINISHED
        race.winner_id = _pick_winner_by_progress(participants)
        race.ended_at = utcnow_naive()
        return race

    submitted_participant_ids = {
        s.participant_id for s in submissions if s.verdict in TERMINAL_VERDICTS
    }
    if participants and all(p.id in submitted_participant_ids for p in participants):
        race.status = RaceStatus.FINISHED
        race.winner_id = _pick_winner_by_progress(participants)
        race.ended_at = utcnow_naive()

    return race


def create_race(db: Session, creator_id: int, race_data: RaceCreate) -> Race:
    problem = _select_problem(db, race_data)
    language = _select_language(db, race_data.language_id)

    race = Race(
        name=race_data.name,
        creator_id=creator_id,
        problem_id=problem.id,
        time_limit=race_data.time_limit,
        status=RaceStatus.WAITING,
    )
    RaceRepository(db).add(race)
    db.flush()

    participant = RaceParticipant(
        race_id=race.id,
        user_id=creator_id,
        language_id=language.id,
    )
    RaceParticipantRepository(db).add(participant)
    db.commit()
    db.refresh(race)
    return race


def get_race(db: Session, race_id: int, user_id: int) -> Race:
    race = _get_race(db, race_id)
    if not any(p.user_id == user_id for p in race.participants):
        raise RaceServiceError(
            status_code=HTTPStatus.FORBIDDEN.value,
            detail="User is not participating in this race",
        )
    _apply_race_end_conditions(db, race)
    db.commit()
    db.refresh(race)
    return race


def get_race_progress(db: Session, race_id: int, user_id: int) -> tuple[Race, list[RaceParticipant], list[RaceSubmission]]:
    race = get_race(db, race_id, user_id)
    participants = RaceParticipantRepository(db).list_for_progress(race_id)
    submissions = RaceSubmissionRepository(db).list_for_progress(race_id)
    return race, participants, submissions


def join_race(
    db: Session,
    race_id: int,
    user_id: int,
    participant_data: RaceParticipantCreate,
) -> RaceParticipant:
    race = _get_race(db, race_id)
    if race.status not in {RaceStatus.WAITING, RaceStatus.READY}:
        raise RaceServiceError(
            status_code=HTTPStatus.BAD_REQUEST.value,
            detail="Race has already started",
        )

    participants = RaceParticipantRepository(db)
    existing = participants.get(race_id, user_id)
    if existing:
        return existing

    language = _select_language(db, participant_data.language_id)
    participant = RaceParticipant(
        race_id=race_id,
        user_id=user_id,
        language_id=language.id,
    )
    participants.add(participant)
    race.status = RaceStatus.WAITING
    db.commit()
    db.refresh(participant)
    return participant


def set_ready(
    db: Session,
    race_id: int,
    user_id: int,
    *,
    is_ready: bool = True,
) -> Race:
    race = _get_race(db, race_id)
    if race.status not in {RaceStatus.WAITING, RaceStatus.READY}:
        raise RaceServiceError(
            status_code=HTTPStatus.BAD_REQUEST.value,
            detail="Race is not accepting ready changes",
        )

    participant = _get_participant(db, race_id, user_id)
    participant.is_ready = is_ready
    db.flush()

    participants = RaceParticipantRepository(db).list_for_race(race_id)
    if len(participants) >= 2 and all(p.is_ready for p in participants):
        race.status = RaceStatus.READY
    else:
        race.status = RaceStatus.WAITING

    db.commit()
    db.refresh(race)
    return race


def start_race(db: Session, race_id: int, user_id: int) -> Race:
    race = _get_race(db, race_id)
    if race.creator_id != user_id:
        raise RaceServiceError(
            status_code=HTTPStatus.FORBIDDEN.value,
            detail="Only the race creator can start the race",
        )
    if race.status != RaceStatus.READY:
        raise RaceServiceError(
            status_code=HTTPStatus.BAD_REQUEST.value,
            detail="Race is not ready to start",
        )

    participants = RaceParticipantRepository(db).list_for_race(race_id)
    if len(participants) < 2:
        raise RaceServiceError(
            status_code=HTTPStatus.BAD_REQUEST.value,
            detail="Race needs at least two participants",
        )
    if not all(p.is_ready for p in participants):
        raise RaceServiceError(
            status_code=HTTPStatus.BAD_REQUEST.value,
            detail="All participants must be ready",
        )

    race.status = RaceStatus.RUNNING
    race.started_at = utcnow_naive()
    db.commit()
    db.refresh(race)
    return race


def change_language(
    db: Session,
    race_id: int,
    user_id: int,
    language_id: int,
) -> RaceParticipant:
    race = _get_race(db, race_id)
    if race.status in {RaceStatus.RUNNING, RaceStatus.FINISHED}:
        raise RaceServiceError(
            status_code=HTTPStatus.BAD_REQUEST.value,
            detail="Race has already started",
        )
    language = _select_language(db, language_id)
    participant = _get_participant(db, race_id, user_id)
    participant.language_id = language.id
    db.commit()
    db.refresh(participant)
    return participant


def submit_race_solution(
    db: Session,
    race_id: int,
    user_id: int,
    data: RaceSubmissionCreate,
) -> RaceSubmission:
    race = _get_race(db, race_id)
    if race.status != RaceStatus.RUNNING:
        raise RaceServiceError(
            status_code=HTTPStatus.BAD_REQUEST.value,
            detail="Race is not running",
        )

    participant = _get_participant(db, race_id, user_id)
    try:
        submission = create_and_queue_submission(
            db,
            user_id,
            SubmissionCreate(
                problem_id=race.problem_id,
                language_id=data.language_id,
                code=data.code,
            ),
        )
    except SubmissionServiceError as exc:
        raise RaceServiceError(
            status_code=exc.status_code,
            detail=exc.detail,
            headers=exc.headers,
        ) from exc

    race_submission = RaceSubmission(
        submission_id=submission.id,
        race_id=race_id,
        participant_id=participant.id,
        problem_id=race.problem_id,
        verdict=submission.status.value,
        code=data.code,
        language_id=data.language_id,
        total_test=submission.total_count,
    )
    RaceSubmissionRepository(db).add(race_submission)
    db.commit()
    db.refresh(race_submission)
    return race_submission


def sync_race_submission(
    db: Session,
    race_id: int,
    user_id: int,
    submission_id: int,
) -> Race:
    race = _get_race(db, race_id)
    _get_participant(db, race_id, user_id)

    race_submission = RaceSubmissionRepository(db).get_by_submission(
        race_id, submission_id
    )
    if not race_submission:
        _raise_not_found("Race submission not found")

    submission = SubmissionRepository(db).get(submission_id)
    if not submission:
        _raise_not_found("Submission not found")

    participant = race_submission.participant
    race_submission.verdict = submission.status.value
    race_submission.total_test = submission.total_count
    participant.progress = submission.passed_count

    if submission.status == SubmissionStatus.ACCEPTED:
        participant.final_status = RaceParticipantStatus.FINISHED

    _apply_race_end_conditions(db, race)

    db.commit()
    db.refresh(race)
    return race


def forfeit_race(db: Session, race_id: int, user_id: int) -> Race:
    race = _get_race(db, race_id)
    if race.status == RaceStatus.FINISHED:
        raise RaceServiceError(
            status_code=HTTPStatus.BAD_REQUEST.value,
            detail="Race has already finished",
        )

    participant = _get_participant(db, race_id, user_id)
    participant.final_status = RaceParticipantStatus.LEFT
    participant.is_ready = False

    active_participants = RaceParticipantRepository(db).list_active_except_user(
        race_id, user_id
    )
    if race.status == RaceStatus.RUNNING:
        if len(active_participants) <= 1:
            race.status = RaceStatus.FINISHED
            race.ended_at = utcnow_naive()
        if len(active_participants) == 1:
            race.winner_id = active_participants[0].user_id
    elif len(active_participants) >= 2 and all(p.is_ready for p in active_participants):
        race.status = RaceStatus.READY
    else:
        race.status = RaceStatus.WAITING

    db.commit()
    db.refresh(race)
    return race
