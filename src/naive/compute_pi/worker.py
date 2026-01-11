from __future__ import annotations

import random
import time

from mpmath import mp

from src.naive.compute_pi.storage import ComputePiStore


def _compute_pi(digits: int) -> str:
    """Return pi to the requested number of digits."""
    mp.dps = digits
    return str(mp.pi)


def main() -> None:
    """Run the naive compute_pi worker loop against the SQLite queue."""
    db_path = "/data/naive.sqlite"
    idle_sleep = 0.2

    store = ComputePiStore(db_path)
    store.init_db()

    while True:
        # Poll for the next queued task; sleep briefly when idle.
        task = store.claim_next_task()
        if task is None:
            time.sleep(idle_sleep)
            continue

        # Compute the full value once, then stream progress by appending digits.
        pi_value = _compute_pi(task.digits)
        total = len(pi_value)
        result = ""
        start_time = time.monotonic()
        for idx, char in enumerate(pi_value, start=1):
            sleep_time = random.uniform(0.1, 0.5)
            time.sleep(sleep_time)
            result += char
            remaining = total - idx
            elapsed = time.monotonic() - start_time
            avg_time = elapsed / idx if idx else 0.0
            eta_seconds = remaining * avg_time
            # Store progress and partial result for the polling client.
            store.update_progress(
                task.task_id,
                progress_current=idx,
                progress_total=total,
                result=result,
                done=False,
                status="RUNNING",
                metrics={
                    "eta_seconds": eta_seconds,
                    "digits_sent": idx,
                    "digits_total": total,
                },
            )

        # Mark completion and persist the final result.
        store.update_progress(
            task.task_id,
            progress_current=total,
            progress_total=total,
            result=result,
            done=True,
            status="COMPLETED",
            metrics={
                "eta_seconds": 0.0,
                "digits_sent": total,
                "digits_total": total,
            },
        )


if __name__ == "__main__":
    main()
