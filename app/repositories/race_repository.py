from typing import List, Optional

from sqlalchemy.orm import Session, joinedload

from app.models.race import Race, RaceParticipant, RaceParticipantStatus, RaceSubmission


class RaceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, race_id: int) -> Optional[Race]:
        return (
            self.db.query(Race)
            .options(
                joinedload(Race.participants),
                joinedload(Race.submissions),
            )
            .filter(Race.id == race_id)
            .first()
        )

    def add(self, race: Race) -> None:
        self.db.add(race)


class RaceParticipantRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, race_id: int, user_id: int) -> Optional[RaceParticipant]:
        return (
            self.db.query(RaceParticipant)
            .filter(
                RaceParticipant.race_id == race_id,
                RaceParticipant.user_id == user_id,
            )
            .first()
        )

    def list_for_race(self, race_id: int) -> List[RaceParticipant]:
        return (
            self.db.query(RaceParticipant)
            .filter(RaceParticipant.race_id == race_id)
            .all()
        )

    def list_for_progress(self, race_id: int) -> List[RaceParticipant]:
        return (
            self.db.query(RaceParticipant)
            .filter(RaceParticipant.race_id == race_id)
            .order_by(RaceParticipant.joined_at.asc())
            .all()
        )

    def list_active_except_user(
        self, race_id: int, user_id: int
    ) -> List[RaceParticipant]:
        return (
            self.db.query(RaceParticipant)
            .filter(
                RaceParticipant.race_id == race_id,
                RaceParticipant.final_status == RaceParticipantStatus.ACTIVE,
                RaceParticipant.user_id != user_id,
            )
            .all()
        )

    def add(self, participant: RaceParticipant) -> None:
        self.db.add(participant)


class RaceSubmissionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_submission(
        self, race_id: int, submission_id: int
    ) -> Optional[RaceSubmission]:
        return (
            self.db.query(RaceSubmission)
            .filter(
                RaceSubmission.race_id == race_id,
                RaceSubmission.submission_id == submission_id,
            )
            .first()
        )

    def list_for_race(self, race_id: int) -> List[RaceSubmission]:
        return (
            self.db.query(RaceSubmission)
            .filter(RaceSubmission.race_id == race_id)
            .all()
        )

    def list_for_progress(self, race_id: int) -> List[RaceSubmission]:
        return (
            self.db.query(RaceSubmission)
            .filter(RaceSubmission.race_id == race_id)
            .order_by(RaceSubmission.started_at.asc())
            .all()
        )

    def add(self, race_submission: RaceSubmission) -> None:
        self.db.add(race_submission)
