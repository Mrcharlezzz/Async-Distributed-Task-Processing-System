from __future__ import annotations

import time

from mpmath import mp

from src.naive.storage import NaiveStore


def _compute_pi(digits: int) -> str:
    mp.dps = digits
    return str(mp.pi)


def main() -> None:
    db_path = "/data/naive.sqlite"
    sleep_per_digit = 0.1
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
            store.update_progress(
                task.task_id,
                progress_current=idx,
                progress_total=total,
                result=result,
                done=False,
                status="RUNNING",
            )
            time.sleep(sleep_per_digit)

        store.update_progress(
            task.task_id,
            progress_current=total,
            progress_total=total,
            result=result,
            done=True,
            status="COMPLETED",
        )


if __name__ == "__main__":
    main()
