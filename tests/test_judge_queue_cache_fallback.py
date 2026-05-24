from types import SimpleNamespace
from unittest.mock import MagicMock

from redis.exceptions import RedisError

import app.services.judge_queue as judge_queue


def _mock_test_case(*, tc_id: int, order: int, is_hidden: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        id=tc_id,
        input=f"in-{tc_id}",
        expected_output=f"out-{tc_id}",
        order=order,
        is_hidden=is_hidden,
    )


def _setup_query_chain(mock_db: MagicMock, rows: list[SimpleNamespace]) -> None:
    query = MagicMock()
    mock_db.query.return_value = query
    query.filter.return_value = query
    query.order_by.return_value = query
    query.all.return_value = rows


def test_get_test_cases_falls_back_to_db_when_cache_read_fails(monkeypatch):
    db = MagicMock()
    rows = [_mock_test_case(tc_id=1, order=1), _mock_test_case(tc_id=2, order=2, is_hidden=True)]
    _setup_query_chain(db, rows)

    monkeypatch.setattr(
        judge_queue,
        "cache_get_sync",
        MagicMock(side_effect=RedisError("redis read down")),
        raising=True,
    )
    cache_set = MagicMock()
    monkeypatch.setattr(judge_queue, "cache_set_sync", cache_set, raising=True)

    result = judge_queue.get_test_cases(db, problem_id=42)

    assert len(result) == 2
    assert result[0]["id"] == 1
    assert result[1]["is_hidden"] is True
    cache_set.assert_called_once()


def test_get_test_cases_returns_data_when_cache_write_fails(monkeypatch):
    db = MagicMock()
    rows = [_mock_test_case(tc_id=1, order=1)]
    _setup_query_chain(db, rows)

    monkeypatch.setattr(judge_queue, "cache_get_sync", MagicMock(return_value=None), raising=True)
    monkeypatch.setattr(
        judge_queue,
        "cache_set_sync",
        MagicMock(side_effect=RedisError("redis write down")),
        raising=True,
    )

    result = judge_queue.get_test_cases(db, problem_id=7)

    assert result == [
        {
            "id": 1,
            "input": "in-1",
            "expected_output": "out-1",
            "order": 1,
            "is_hidden": False,
        }
    ]
