"""
Background worker that pulls submission ids off a Redis queue and judges them.

Uses BRPOP (blocking pop) instead of polling postgres — way less overhead
and submissions start processing almost instantly after being enqueued.
Run multiple instances for horizontal scaling; each worker gets its own job.
"""

import time
import signal
from typing import Optional

from app.db.session import SessionLocal
from app.models.submission import Submission, SubmissionStatus
from app.services.judge_queue import judge_submission
from app.cache.redis import dequeue_submission, close_sync_pool


class JudgeWorker:
    def __init__(
        self,
        worker_id: Optional[str] = None,
    ):
        self.worker_id = worker_id or f"worker-{id(self)}"
        self.running = False
        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)

    def _shutdown(self, signum, frame):
        print(f"\n[{self.worker_id}] Shutting down...")
        self.running = False

    def _process(self, submission_id: int):
        db = SessionLocal()
        try:
            submission = db.query(Submission).filter(Submission.id == submission_id).first()
            if not submission:
                print(f"[{self.worker_id}] Submission {submission_id} not found, skipping")
                return

            # guard against duplicate processing if somehow enqueued twice
            if submission.status != SubmissionStatus.PENDING:
                print(f"[{self.worker_id}] Submission {submission_id} already {submission.status.value}, skipping")
                return

            print(f"[{self.worker_id}] Processing {submission_id}")
            start = time.perf_counter()

            try:
                judge_submission(db, submission)
                elapsed = (time.perf_counter() - start) * 1000
                print(
                    f"[{self.worker_id}] {submission_id}: {submission.status.value} "
                    f"({submission.passed_count}/{submission.total_count}) in {elapsed:.0f}ms"
                )
            except Exception as e:
                print(f"[{self.worker_id}] Error on {submission_id}: {e}")
                submission.status = SubmissionStatus.RUNTIME_ERROR
                submission.results = [{"error": str(e)}]
                db.commit()
        finally:
            db.close()

    def run(self):
        print(f"[{self.worker_id}] Starting (Redis queue mode)...")
        self.running = True

        while self.running:
            # 5s timeout so the loop can check self.running for graceful shutdown
            submission_id = dequeue_submission(timeout=5)
            if submission_id is not None:
                self._process(submission_id)

        close_sync_pool()
        print(f"[{self.worker_id}] Stopped.")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Judge worker (Redis queue)")
    parser.add_argument("--worker-id", type=str, default=None)
    args = parser.parse_args()

    worker = JudgeWorker(worker_id=args.worker_id)
    worker.run()


if __name__ == "__main__":
    main()
