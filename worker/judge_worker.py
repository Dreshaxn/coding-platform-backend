"""
Background worker for processing code submissions.

This worker polls the database for pending submissions and judges them.
It's designed to run as a separate process (or multiple processes for scaling).

Features:
- Graceful shutdown on SIGTERM/SIGINT
- Exponential backoff when idle (reduces DB load)
- Row-level locking to prevent duplicate processing
"""

import time
import signal
from typing import Optional

from app.db.session import SessionLocal
from app.models.submission import Submission, SubmissionStatus
from app.services.judge_queue import judge_submission


class JudgeWorker:
    """
    Continuously processes pending submissions from the database.
    
    The worker uses PostgreSQL's SELECT FOR UPDATE SKIP LOCKED to safely
    claim submissions without conflicts when running multiple workers.
    """
    
    def __init__(
        self,
        poll_interval: float = 1.0,
        batch_size: int = 5,
        worker_id: Optional[str] = None,
    ):
        self.poll_interval = poll_interval
        self.batch_size = batch_size
        self.worker_id = worker_id or f"worker-{id(self)}"
        self.running = False
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)

    def _shutdown(self, signum, frame):
        """Handle shutdown signals gracefully."""
        print(f"\n[{self.worker_id}] Shutting down...")
        self.running = False

    def _get_pending(self, db):
        """
        Fetch pending submissions with row-level locking.
        
        SKIP LOCKED ensures multiple workers don't process the same submission.
        This is key for horizontal scaling.
        """
        return (
            db.query(Submission)
            .filter(Submission.status == SubmissionStatus.PENDING)
            .order_by(Submission.created_at.asc())  # FIFO ordering
            .limit(self.batch_size)
            .with_for_update(skip_locked=True)
            .all()
        )

    def _process(self, db, submission: Submission):
        """Judge a single submission and log the result."""
        print(f"[{self.worker_id}] Processing {submission.id}")
        start = time.perf_counter()

        try:
            judge_submission(db, submission)
            elapsed = (time.perf_counter() - start) * 1000
            print(
                f"[{self.worker_id}] {submission.id}: {submission.status.value} "
                f"({submission.passed_count}/{submission.total_count}) in {elapsed:.0f}ms"
            )
        except Exception as e:
            print(f"[{self.worker_id}] Error on {submission.id}: {e}")
            submission.status = SubmissionStatus.RUNTIME_ERROR
            submission.results = [{"error": str(e)}]
            db.commit()

    def run_once(self) -> int:
        """Process one batch of submissions. Returns count processed."""
        db = SessionLocal()
        try:
            submissions = self._get_pending(db)
            for s in submissions:
                self._process(db, s)
            return len(submissions)
        finally:
            db.close()

    def run(self):
        """
        Main loop - continuously process submissions.
        
        Uses exponential backoff when idle to reduce database load.
        Backs off from 1s up to 10s between polls when no work is found.
        """
        print(f"[{self.worker_id}] Starting...")
        self.running = True
        idle_count = 0

        while self.running:
            processed = self.run_once()
            
            if processed == 0:
                # No work found - back off exponentially
                idle_count += 1
                sleep_time = min(self.poll_interval * (1.5 ** min(idle_count, 10)), 10.0)
                time.sleep(sleep_time)
            else:
                # Work found - reset backoff and poll again quickly
                idle_count = 0
                time.sleep(0.1)

        print(f"[{self.worker_id}] Stopped.")


def main():
    """CLI entry point for running the worker."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Code submission judge worker")
    parser.add_argument("--poll-interval", type=float, default=1.0,
                        help="Base polling interval in seconds")
    parser.add_argument("--batch-size", type=int, default=5,
                        help="Max submissions to process per batch")
    parser.add_argument("--worker-id", type=str, default=None,
                        help="Unique worker identifier for logging")
    parser.add_argument("--once", action="store_true",
                        help="Process one batch and exit")
    args = parser.parse_args()

    worker = JudgeWorker(args.poll_interval, args.batch_size, args.worker_id)

    if args.once:
        print(f"Processed {worker.run_once()} submissions")
    else:
        worker.run()


if __name__ == "__main__":
    main()
