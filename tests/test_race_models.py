from app.models.race import (
    Race,
    RaceParticipant,
    RaceParticipantStatus,
    RaceStatus,
    RaceSubmission,
)


def test_race_tables_are_registered_with_expected_columns():
    assert Race.__tablename__ == "races"
    assert RaceParticipant.__tablename__ == "race_participants"
    assert RaceSubmission.__tablename__ == "race_submissions"

    race_columns = Race.__table__.columns.keys()
    assert "creator_id" in race_columns
    assert "problem_id" in race_columns
    assert "time_limit" in race_columns
    assert "started_at" in race_columns
    assert "ended_at" in race_columns

    participant_columns = RaceParticipant.__table__.columns.keys()
    assert "race_id" in participant_columns
    assert "is_ready" in participant_columns
    assert "user_id" in participant_columns
    assert "language_id" in participant_columns
    assert "progress" in participant_columns
    assert "final_status" in participant_columns

    submission_columns = RaceSubmission.__table__.columns.keys()
    assert "submission_id" in submission_columns
    assert "race_id" in submission_columns
    assert "participant_id" in submission_columns
    assert "problem_id" in submission_columns
    assert "verdict" in submission_columns
    assert "code" in submission_columns
    assert "started_at" in submission_columns
    assert "language_id" in submission_columns
    assert "total_test" in submission_columns


def test_race_status_values_match_api_contract():
    assert RaceStatus.WAITING.value == "waiting"
    assert RaceStatus.RUNNING.value == "running"
    assert RaceStatus.FINISHED.value == "finished"
    assert RaceParticipantStatus.ACTIVE.value == "active"
    assert RaceParticipantStatus.DISQUALIFIED.value == "disqualified"
