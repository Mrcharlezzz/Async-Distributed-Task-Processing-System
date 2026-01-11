from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class NaiveTaskRow:
    task_id: str
    digits: int
    demo: bool
    status: str
    progress_current: int
    progress_total: int
    result: str
    done: bool
    metrics: dict | None
    created_at: str
    updated_at: str


class ComputePiStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=1)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS naive_tasks (
                    task_id TEXT PRIMARY KEY,
                    digits INTEGER NOT NULL,
                    demo INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    progress_current INTEGER NOT NULL,
                    progress_total INTEGER NOT NULL,
                    result TEXT NOT NULL,
                    done INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metrics TEXT
                )
                """
            )
            columns = {row[1] for row in conn.execute("PRAGMA table_info(naive_tasks)")}
            if "metrics" not in columns:
                conn.execute("ALTER TABLE naive_tasks ADD COLUMN metrics TEXT")
            if "demo" not in columns:
                conn.execute("ALTER TABLE naive_tasks ADD COLUMN demo INTEGER NOT NULL DEFAULT 0")

    def create_task(self, task_id: str, digits: int, demo: bool = False) -> None:
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO naive_tasks (
                    task_id, digits, demo, status, progress_current, progress_total,
                    result, done, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (task_id, digits, 1 if demo else 0, "QUEUED", 0, digits, "", 0, now, now),
            )

    def get_task(self, task_id: str) -> NaiveTaskRow | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM naive_tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        if row is None:
            return None
        return NaiveTaskRow(
            task_id=row["task_id"],
            digits=row["digits"],
            demo=bool(row["demo"]),
            status=row["status"],
            progress_current=row["progress_current"],
            progress_total=row["progress_total"],
            result=row["result"],
            done=bool(row["done"]),
            metrics=json.loads(row["metrics"]) if row["metrics"] else None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def claim_next_task(self) -> NaiveTaskRow | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM naive_tasks
                WHERE done = 0 AND status = 'QUEUED'
                ORDER BY created_at ASC
                LIMIT 1
                """
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                """
                UPDATE naive_tasks
                SET status = 'RUNNING', updated_at = ?
                WHERE task_id = ?
                """,
                (_utc_now(), row["task_id"]),
            )
        return self.get_task(row["task_id"])

    def update_progress(
        self,
        task_id: str,
        *,
        progress_current: int,
        progress_total: int,
        result: str,
        done: bool,
        status: str,
        metrics: dict | None = None,
    ) -> None:
        metrics_json = json.dumps(metrics) if metrics is not None else None
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE naive_tasks
                SET progress_current = ?, progress_total = ?, result = ?,
                    done = ?, status = ?, updated_at = ?, metrics = ?
                WHERE task_id = ?
                """,
                (
                    progress_current,
                    progress_total,
                    result,
                    1 if done else 0,
                    status,
                    _utc_now(),
                    metrics_json,
                    task_id,
                ),
            )

    def delete_task(self, task_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM naive_tasks WHERE task_id = ?", (task_id,))
