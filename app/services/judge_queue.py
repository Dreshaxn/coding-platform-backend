"""
Submission judging service.

This module orchestrates the judging process:
1. Retrieves test cases for the problem
2. Calls the execution engine to run user code
3. Maps execution results to submission status
4. Updates the database with results

It acts as a bridge between the API layer and the execution engine,
handling caching and result formatting.
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.submission import Submission, SubmissionStatus
from app.models.test_case import TestCase
from app.models.language import Language
# Import from concrete modules to avoid circular imports:
# judge_queue is used by the API routes, and importing the worker package would
# also import the background worker (which imports judge_queue).
from worker.executor import run_code, ExecutionResult
from worker.config import ExecutionStatus


# Maps execution engine statuses to submission statuses
STATUS_MAP: Dict[ExecutionStatus, SubmissionStatus] = {
    ExecutionStatus.SUCCESS: SubmissionStatus.ACCEPTED,
    ExecutionStatus.WRONG_ANSWER: SubmissionStatus.WRONG_ANSWER,
    ExecutionStatus.TIME_LIMIT_EXCEEDED: SubmissionStatus.TIME_LIMIT_EXCEEDED,
    ExecutionStatus.MEMORY_LIMIT_EXCEEDED: SubmissionStatus.MEMORY_LIMIT_EXCEEDED,
    ExecutionStatus.RUNTIME_ERROR: SubmissionStatus.RUNTIME_ERROR,
    ExecutionStatus.COMPILATION_ERROR: SubmissionStatus.COMPILATION_ERROR,
    ExecutionStatus.INTERNAL_ERROR: SubmissionStatus.RUNTIME_ERROR,
}


# =============================================================================
# TEST CASE CACHING
# =============================================================================

# In-memory cache for test cases to avoid repeated DB queries.
# For production, consider Redis for shared cache across workers.
_test_case_cache: Dict[int, List[Dict[str, Any]]] = {}


def get_test_cases(
    db: Session,
    problem_id: int,
    force_refresh: bool = False,
) -> List[Dict[str, Any]]:
    """
    Retrieve test cases for a problem, using cache when available.
    
    Caching is important because test cases rarely change but are
    queried for every submission to a problem.
    """
    if not force_refresh and problem_id in _test_case_cache:
        return _test_case_cache[problem_id]
    
    test_cases = (
        db.query(TestCase)
        .filter(TestCase.problem_id == problem_id)
        .order_by(TestCase.order)
        .all()
    )
    
    _test_case_cache[problem_id] = [
        {
            "id": tc.id,
            "input": tc.input,
            "expected_output": tc.expected_output,
            "order": tc.order,
            "is_hidden": tc.is_hidden,
        }
        for tc in test_cases
    ]
    
    return _test_case_cache[problem_id]


def invalidate_cache(problem_id: Optional[int] = None) -> None:
    """
    Clear cached test cases.
    
    Call this when test cases are added/modified/deleted.
    """
    if problem_id is not None:
        _test_case_cache.pop(problem_id, None)
    else:
        _test_case_cache.clear()


# =============================================================================
# SUBMISSION JUDGING
# =============================================================================

def judge_submission(
    db: Session,
    submission: Submission,
    test_cases: Optional[List[Dict[str, Any]]] = None,
) -> Submission:
    """
    Judge a submission by executing code against test cases.
    
    This is the main entry point called by the worker. It:
    1. Marks submission as RUNNING
    2. Loads test cases (from cache or DB)
    3. Executes code via the Docker execution engine
    4. Updates submission with results
    
    Returns the updated submission object.
    """
    submission.status = SubmissionStatus.RUNNING
    db.commit()
    
    if test_cases is None:
        test_cases = get_test_cases(db, submission.problem_id)
    
    # Edge case: problem has no test cases
    if not test_cases:
        return _accept_submission(db, submission)
    
    # Validate language exists
    language = db.query(Language).filter(Language.id == submission.language_id).first()
    if not language:
        return _fail_submission(db, submission, "Language not found")
    
    # Execute code against all test cases
    exec_result = run_code(
        code=submission.code,
        language_slug=language.slug,
        test_inputs=[tc["input"] for tc in test_cases],
        expected_outputs=[tc["expected_output"] for tc in test_cases],
    )
    
    return _process_results(db, submission, test_cases, exec_result)


def _accept_submission(db: Session, submission: Submission) -> Submission:
    """Mark submission as accepted (for problems with no test cases)."""
    submission.status = SubmissionStatus.ACCEPTED
    submission.passed = True
    submission.passed_count = 0
    submission.total_count = 0
    submission.results = []
    db.commit()
    return submission


def _fail_submission(db: Session, submission: Submission, error: str) -> Submission:
    """Mark submission as failed with an error message."""
    submission.status = SubmissionStatus.RUNTIME_ERROR
    submission.passed = False
    submission.results = [{"error": error}]
    db.commit()
    return submission


def _process_results(
    db: Session,
    submission: Submission,
    test_cases: List[Dict[str, Any]],
    exec_result: ExecutionResult,
) -> Submission:
    """
    Process execution results and update the submission.
    
    Formats results for the API response, hiding details of hidden test cases
    while providing useful feedback for visible ones.
    """
    results = []
    
    for tc, test_result in zip(test_cases, exec_result.test_results):
        detail = {
            "test_case_id": tc["id"],
            "order": tc["order"],
            "is_hidden": tc["is_hidden"],
            "status": test_result.status.value,
            "runtime_ms": test_result.runtime_ms,
            "memory_kb": test_result.memory_kb,
            "exit_code": test_result.exit_code,
        }
        
        # Only expose I/O details for visible (sample) test cases
        if not tc["is_hidden"]:
            detail["input"] = tc["input"][:500]
            detail["expected_output"] = tc["expected_output"][:500]
            detail["actual_output"] = test_result.stdout[:500]
            if test_result.stderr:
                detail["stderr"] = test_result.stderr[:500]
        
        results.append(detail)
    
    # Update submission fields
    submission.status = STATUS_MAP.get(exec_result.status, SubmissionStatus.RUNTIME_ERROR)
    submission.passed = exec_result.status == ExecutionStatus.SUCCESS
    submission.passed_count = exec_result.passed_count
    submission.total_count = exec_result.total_count
    submission.results = results
    
    # Prepend compilation errors if any
    if exec_result.compilation_output:
        submission.results = [
            {"compilation_error": exec_result.compilation_output[:2000]}
        ] + results
    
    db.commit()
    db.refresh(submission)
    return submission


# =============================================================================
# LEGACY ALIASES
# =============================================================================

# Backward compatibility - remove once all code migrates to snake_case
getCachedTestCases = get_test_cases
invalidateTestCaseCache = invalidate_cache
judgeSubmission = judge_submission
