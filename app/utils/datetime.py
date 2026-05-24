from datetime import UTC, datetime


def utcnow_naive() -> datetime:
    """Return a UTC timestamp without tzinfo for naive DB DateTime columns."""
    return datetime.now(UTC).replace(tzinfo=None)
