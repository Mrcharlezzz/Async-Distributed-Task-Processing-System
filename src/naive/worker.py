from __future__ import annotations

import random
import time

from mpmath import mp

from src.naive.storage import NaiveStore


def _compute_pi(digits: int) -> str:
    mp.dps = digits
    return str(mp.pi)


def main() -> None:
    db_path = "/data/naive.sqlite"
    idle_sleep = 0.2

    store = NaiveStore(db_path)
    store.init_db()

    while True:
        task = store.claim_next_task()
        if task is None:
            time.sleep(idle_sleep)
            continue

        pi_value = _compute_pi(task.digits)
        total = len(pi_value)
        result = ""
        for idx, char in enumerate(pi_value, start=1):
            result += char
            sleep_time = random.uniform(0.02, 0.2)
            remaining = total - idx
            eta_seconds = remaining * sleep_time
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
            time.sleep(sleep_time)

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
