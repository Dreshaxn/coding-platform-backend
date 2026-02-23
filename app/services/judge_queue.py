"""
Submission judging — bridges the API layer and the docker execution engine.

Test cases are cached in Redis so we don't hit postgres on every submission
to the same problem. Status updates are published via Redis pub/sub so the
websocket layer can push live progress to the client.
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.submission import Submission, SubmissionStatus
from app.models.problem import Problem
from app.models.test_case import TestCase
from app.models.language import Language
from worker.executor import run_code, ExecutionResult
from worker.config import ExecutionStatus
from app.cache.redis import cache_get_sync, cache_set_sync, cache_delete_sync, publish_status_sync

# maps execution engine statuses -> submission statuses
STATUS_MAP: Dict[ExecutionStatus, SubmissionStatus] = {
    ExecutionStatus.SUCCESS: SubmissionStatus.ACCEPTED,
    ExecutionStatus.WRONG_ANSWER: SubmissionStatus.WRONG_ANSWER,
    ExecutionStatus.TIME_LIMIT_EXCEEDED: SubmissionStatus.TIME_LIMIT_EXCEEDED,
    ExecutionStatus.MEMORY_LIMIT_EXCEEDED: SubmissionStatus.MEMORY_LIMIT_EXCEEDED,
    ExecutionStatus.RUNTIME_ERROR: SubmissionStatus.RUNTIME_ERROR,
    ExecutionStatus.COMPILATION_ERROR: SubmissionStatus.COMPILATION_ERROR,
    ExecutionStatus.INTERNAL_ERROR: SubmissionStatus.RUNTIME_ERROR,
}

TERMINAL_STATUSES = {
    SubmissionStatus.ACCEPTED,
    SubmissionStatus.WRONG_ANSWER,
    SubmissionStatus.TIME_LIMIT_EXCEEDED,
    SubmissionStatus.MEMORY_LIMIT_EXCEEDED,
    SubmissionStatus.RUNTIME_ERROR,
    SubmissionStatus.COMPILATION_ERROR,
}


def get_test_cases(
    db: Session,
    problem_id: int,
    force_refresh: bool = False,
) -> List[Dict[str, Any]]:
    """Fetch test cases with a 1-hour Redis cache — they rarely change."""
    cache_key = f"cache:testcases:{problem_id}"

    if not force_refresh:
        cached = cache_get_sync(cache_key)
        if cached is not None:
            return cached

    test_cases = (
        db.query(TestCase)
        .filter(TestCase.problem_id == problem_id)
        .order_by(TestCase.order)
        .all()
    )

    serialized = [
        {
            "id": tc.id,
            "input": tc.input,
            "expected_output": tc.expected_output,
            "order": tc.order,
            "is_hidden": tc.is_hidden,
        }
        for tc in test_cases
    ]

    cache_set_sync(cache_key, serialized, ttl=3600)
    return serialized


def invalidate_cache(problem_id: Optional[int] = None) -> None:
    """Call when test cases are added/modified/deleted."""
    if problem_id is not None:
        cache_delete_sync(f"cache:testcases:{problem_id}")
    # full cache clear would require SCAN — not worth it since test case
    # edits are always scoped to a single problem in practice


def judge_submission(
    db: Session,
    submission: Submission,
    test_cases: Optional[List[Dict[str, Any]]] = None,
) -> Submission:
    """Main entry point — called by the judge worker after dequeueing a job."""
    submission.status = SubmissionStatus.RUNNING
    db.commit()

    publish_status_sync(submission.id, {
        "status": SubmissionStatus.RUNNING.value,
        "submission_id": submission.id,
    })

    if test_cases is None:
        test_cases = get_test_cases(db, submission.problem_id)

    if not test_cases:
        return _accept_submission(db, submission)

    language = db.query(Language).filter(Language.id == submission.language_id).first()
    if not language:
        return _fail_submission(db, submission, "Language not found")

    problem = db.query(Problem).filter(Problem.id == submission.problem_id).first()
    function_name = problem.function_name if problem else None

    exec_result = run_code(
        code=submission.code,
        language_slug=language.slug,
        test_inputs=[tc["input"] for tc in test_cases],
        expected_outputs=[tc["expected_output"] for tc in test_cases],
        function_name=function_name,
    )

    return _process_results(db, submission, test_cases, exec_result)


def _accept_submission(db: Session, submission: Submission) -> Submission:
    submission.status = SubmissionStatus.ACCEPTED
    submission.passed = True
    submission.passed_count = 0
    submission.total_count = 0
    submission.results = []
    db.commit()

    publish_status_sync(submission.id, {
        "status": SubmissionStatus.ACCEPTED.value,
        "submission_id": submission.id,
        "passed": True,
        "passed_count": 0,
        "total_count": 0,
    })

    return submission


def _fail_submission(db: Session, submission: Submission, error: str) -> Submission:
    submission.status = SubmissionStatus.RUNTIME_ERROR
    submission.passed = False
    submission.results = [{"error": error}]
    db.commit()

    publish_status_sync(submission.id, {
        "status": SubmissionStatus.RUNTIME_ERROR.value,
        "submission_id": submission.id,
        "passed": False,
        "error": error,
    })

    return submission


def _process_results(
    db: Session,
    submission: Submission,
    test_cases: List[Dict[str, Any]],
    exec_result: ExecutionResult,
) -> Submission:
    results = []

    for i, (tc, test_result) in enumerate(zip(test_cases, exec_result.test_results)):
        detail = {
            "test_case_id": tc["id"],
            "order": tc["order"],
            "is_hidden": tc["is_hidden"],
            "status": test_result.status.value,
            "runtime_ms": test_result.runtime_ms,
            "memory_kb": test_result.memory_kb,
            "exit_code": test_result.exit_code,
        }

        # only expose i/o for visible (sample) test cases, not the hidden ones
        if not tc["is_hidden"]:
            detail["input"] = tc["input"][:500]
            detail["expected_output"] = tc["expected_output"][:500]
            detail["actual_output"] = test_result.stdout[:500]
            if test_result.stderr:
                detail["stderr"] = test_result.stderr[:500]

        results.append(detail)

        # per-test progress so the frontend can show a live test counter
        publish_status_sync(submission.id, {
            "type": "test_result",
            "submission_id": submission.id,
            "test_index": i,
            "test_status": test_result.status.value,
            "runtime_ms": test_result.runtime_ms,
            "passed_so_far": sum(
                1 for r in results if r["status"] == ExecutionStatus.SUCCESS.value
            ),
            "total_so_far": len(results),
        })

    submission.status = STATUS_MAP.get(exec_result.status, SubmissionStatus.RUNTIME_ERROR)
    submission.passed = exec_result.status == ExecutionStatus.SUCCESS
    submission.passed_count = exec_result.passed_count
    submission.total_count = exec_result.total_count
    submission.results = results

    if exec_result.compilation_output:
        submission.results = [
            {"compilation_error": exec_result.compilation_output[:2000]}
        ] + results

    db.commit()
    db.refresh(submission)

    # publish final verdict
    publish_status_sync(submission.id, {
        "status": submission.status.value,
        "submission_id": submission.id,
        "passed": submission.passed,
        "passed_count": submission.passed_count,
        "total_count": submission.total_count,
    })

    return submission
