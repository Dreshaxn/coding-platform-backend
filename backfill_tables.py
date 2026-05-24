"""Backfill missing rows in key tables using existing data.

Currently fills:
- user_stats for existing users
- problem_templates for existing problems/languages

This script is idempotent: running it multiple times will not duplicate rows.
"""

from __future__ import annotations

import argparse
import keyword
import re
from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import (
    Difficulty,
    Language,
    Problem,
    ProblemTemplate,
    Submission,
    SubmissionStatus,
    TestCase,
    User,
    UserSolvedProblem,
    UserStats,
)

PLACEHOLDER_INPUT = "__PLACEHOLDER_INPUT__"
PLACEHOLDER_OUTPUT = "__PLACEHOLDER_OUTPUT__"


def _python_template(function_name: str | None) -> str:
    if function_name:
        return (
            "class Solution:\n"
            f"    def {function_name}(self, *args):\n"
            "        # TODO: implement\n"
            "        pass\n"
        )
    return (
        "# Read from stdin and write to stdout.\n"
        "# Example:\n"
        "# data = input().strip()\n"
        "# print(data)\n"
    )


def _java_template(function_name: str | None) -> str:
    if function_name:
        return (
            "class Solution {\n"
            f"    public Object {function_name}(Object... args) {{\n"
            "        // TODO: implement\n"
            "        return null;\n"
            "    }\n"
            "}\n"
        )
    return (
        "import java.io.*;\n\n"
        "public class Solution {\n"
        "    public static void main(String[] args) throws Exception {\n"
        "        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));\n"
        "        // TODO: parse stdin and print answer\n"
        "    }\n"
        "}\n"
    )


def _c_template(function_name: str | None) -> str:
    if function_name:
        return (
            "#include <stdio.h>\n\n"
            f"int {function_name}(void) {{\n"
            "    // TODO: implement\n"
            "    return 0;\n"
            "}\n"
        )
    return (
        "#include <stdio.h>\n\n"
        "int main(void) {\n"
        "    // TODO: read from stdin and print to stdout\n"
        "    return 0;\n"
        "}\n"
    )


def _default_template(language: Language, function_name: str | None) -> str:
    slug = (language.slug or "").lower()
    if slug in {"python", "python3"}:
        return _python_template(function_name)
    if slug == "java":
        return _java_template(function_name)
    if slug == "c":
        return _c_template(function_name)

    if language.boilerplate_code:
        return language.boilerplate_code

    return "// TODO: implement solution\n"


def _to_camel_case_identifier(title: str) -> str:
    """
    Convert a problem title into a safe camelCase Python identifier.
    """
    parts = re.findall(r"[A-Za-z0-9]+", title or "")
    if not parts:
        candidate = "solve"
    else:
        first = parts[0].lower()
        rest = [p.capitalize() for p in parts[1:]]
        candidate = first + "".join(rest)

    # Python identifiers cannot start with a digit.
    if candidate and candidate[0].isdigit():
        candidate = f"p{candidate}"

    # Avoid reserved keywords like "class", "def", etc.
    if keyword.iskeyword(candidate):
        candidate = f"{candidate}_fn"

    return candidate or "solve"


def backfill_function_names(
    db: Session, *, dry_run: bool, update_existing: bool
) -> tuple[int, int]:
    """
    Populate missing Problem.function_name values from problem titles.

    When update_existing=True, normalize existing function names too.
    """
    problems = db.query(Problem).order_by(Problem.id.asc()).all()
    used_names: set[str] = set()
    created = 0
    updated = 0

    # Reserve already existing names first (unless we are updating all).
    if not update_existing:
        for problem in problems:
            if problem.function_name:
                used_names.add(problem.function_name)

    for problem in problems:
        needs_value = problem.function_name is None
        if not needs_value and not update_existing:
            continue

        base_name = _to_camel_case_identifier(problem.title)
        candidate = base_name
        suffix = 2
        while candidate in used_names:
            candidate = f"{base_name}{suffix}"
            suffix += 1

        if problem.function_name != candidate:
            problem.function_name = candidate
            if needs_value:
                created += 1
            else:
                updated += 1

        used_names.add(candidate)

    return created, updated


def backfill_user_stats(db: Session, *, dry_run: bool, update_existing: bool) -> tuple[int, int]:
    users = db.query(User).all()
    created = 0
    updated = 0

    for user in users:
        stats = db.query(UserStats).filter(UserStats.user_id == user.id).first()
        if stats and not update_existing:
            continue

        total_submissions = (
            db.query(func.count(Submission.id))
            .filter(Submission.user_id == user.id)
            .scalar()
            or 0
        )
        accepted_submissions = (
            db.query(func.count(Submission.id))
            .filter(
                Submission.user_id == user.id,
                Submission.status == SubmissionStatus.ACCEPTED,
            )
            .scalar()
            or 0
        )
        problems_solved = (
            db.query(func.count(UserSolvedProblem.id))
            .filter(UserSolvedProblem.user_id == user.id)
            .scalar()
            or 0
        )
        last_submission_at = (
            db.query(func.max(Submission.created_at))
            .filter(Submission.user_id == user.id)
            .scalar()
        )

        solved_by_difficulty = (
            db.query(Difficulty.name, func.count(UserSolvedProblem.id))
            .join(Problem, Problem.difficulty_id == Difficulty.id)
            .join(UserSolvedProblem, UserSolvedProblem.problem_id == Problem.id)
            .filter(UserSolvedProblem.user_id == user.id)
            .group_by(Difficulty.name)
            .all()
        )
        easy_solved = 0
        medium_solved = 0
        hard_solved = 0
        for difficulty_name, count in solved_by_difficulty:
            name = (difficulty_name or "").lower()
            if name == "easy":
                easy_solved = count
            elif name == "medium":
                medium_solved = count
            elif name == "hard":
                hard_solved = count

        xp = accepted_submissions * 10

        if stats is None:
            stats = UserStats(
                user_id=user.id,
                xp=xp,
                streak=0,
                longest_streak=0,
                problems_solved=problems_solved,
                easy_solved=easy_solved,
                medium_solved=medium_solved,
                hard_solved=hard_solved,
                total_submissions=total_submissions,
                accepted_submissions=accepted_submissions,
                last_submission_at=last_submission_at,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            if not dry_run:
                db.add(stats)
            created += 1
        else:
            stats.xp = xp
            stats.problems_solved = problems_solved
            stats.easy_solved = easy_solved
            stats.medium_solved = medium_solved
            stats.hard_solved = hard_solved
            stats.total_submissions = total_submissions
            stats.accepted_submissions = accepted_submissions
            stats.last_submission_at = last_submission_at
            stats.updated_at = datetime.now(UTC)
            updated += 1

    return created, updated


def backfill_problem_templates(db: Session, *, dry_run: bool) -> int:
    problems = db.query(Problem).all()
    languages = db.query(Language).filter(Language.is_active.is_(True)).all()
    created = 0

    for problem in problems:
        for language in languages:
            existing = (
                db.query(ProblemTemplate)
                .filter(
                    ProblemTemplate.problem_id == problem.id,
                    ProblemTemplate.language_id == language.id,
                )
                .first()
            )
            if existing:
                continue

            template = ProblemTemplate(
                problem_id=problem.id,
                language_id=language.id,
                boilerplate_code=_default_template(language, problem.function_name),
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            if not dry_run:
                db.add(template)
            created += 1

    return created


def backfill_test_cases(db: Session, *, dry_run: bool) -> int:
    """
    Ensure every problem has at least one test case.

    Backfilled rows are intentionally hidden placeholders and should be replaced
    with real problem-specific tests as content is curated.
    """
    problems = db.query(Problem).all()
    created = 0

    for problem in problems:
        has_test_cases = (
            db.query(TestCase.id)
            .filter(TestCase.problem_id == problem.id)
            .first()
            is not None
        )
        if has_test_cases:
            continue

        placeholder = TestCase(
            problem_id=problem.id,
            input=PLACEHOLDER_INPUT,
            expected_output=PLACEHOLDER_OUTPUT,
            is_hidden=True,
            order=1,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        if not dry_run:
            db.add(placeholder)
        created += 1

    return created


def upgrade_placeholder_test_cases(db: Session, *, dry_run: bool) -> int:
    """
    Replace placeholder test cases with generic starter samples.

    These are scaffolding samples only; they should be replaced with
    problem-specific tests for production-quality judging.
    """
    placeholders = (
        db.query(TestCase)
        .join(Problem, Problem.id == TestCase.problem_id)
        .filter(
            TestCase.input == PLACEHOLDER_INPUT,
            TestCase.expected_output == PLACEHOLDER_OUTPUT,
        )
        .all()
    )

    updated = 0
    for tc in placeholders:
        problem = db.query(Problem).filter(Problem.id == tc.problem_id).first()
        if not problem:
            continue

        if problem.function_name:
            tc.input = "[2, 7, 11, 15]\n9"
            tc.expected_output = "[0, 1]"
        else:
            tc.input = "42\n"
            tc.expected_output = "42"

        tc.is_hidden = False
        tc.order = 1
        tc.updated_at = datetime.now(UTC)
        updated += 1

    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill missing table rows")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be inserted/updated without writing to DB.",
    )
    parser.add_argument(
        "--update-existing-stats",
        action="store_true",
        help="Also recompute and update existing user_stats rows.",
    )
    parser.add_argument(
        "--upgrade-placeholder-tests",
        action="store_true",
        help=(
            "Replace __PLACEHOLDER__ test cases with generic starter samples. "
            "Use only as temporary scaffolding."
        ),
    )
    parser.add_argument(
        "--backfill-function-names",
        action="store_true",
        help="Populate missing problems.function_name from problem titles.",
    )
    parser.add_argument(
        "--update-existing-function-names",
        action="store_true",
        help="Recompute function_name for all problems (not just missing).",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        stats_created, stats_updated = backfill_user_stats(
            db, dry_run=args.dry_run, update_existing=args.update_existing_stats
        )
        fn_created = 0
        fn_updated = 0
        if args.backfill_function_names or args.update_existing_function_names:
            fn_created, fn_updated = backfill_function_names(
                db,
                dry_run=args.dry_run,
                update_existing=args.update_existing_function_names,
            )
        templates_created = backfill_problem_templates(db, dry_run=args.dry_run)
        test_cases_created = backfill_test_cases(db, dry_run=args.dry_run)
        placeholder_tests_upgraded = 0
        if args.upgrade_placeholder_tests:
            placeholder_tests_upgraded = upgrade_placeholder_test_cases(
                db, dry_run=args.dry_run
            )

        if args.dry_run:
            db.rollback()
        else:
            db.commit()

        print(
            f"user_stats created={stats_created}, updated={stats_updated}; "
            f"function_names created={fn_created}, updated={fn_updated}; "
            f"problem_templates created={templates_created}; "
            f"test_cases created={test_cases_created}; "
            f"placeholder_tests_upgraded={placeholder_tests_upgraded}"
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
