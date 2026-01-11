from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class NaiveDocTaskRow:
    task_id: str
    document_path: str
    document_url: str | None
    keywords: list[str]
    demo: bool
    status: str
    progress_current: int
    progress_total: int
    done: bool
    metrics: dict | None
    last_snippet_id: int
    created_at: str
    updated_at: str


class DocumentAnalysisStore:
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
                CREATE TABLE IF NOT EXISTS naive_doc_tasks (
                    task_id TEXT PRIMARY KEY,
                    document_path TEXT NOT NULL,
                    document_url TEXT,
                    keywords TEXT NOT NULL,
                    demo INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    progress_current INTEGER NOT NULL,
                    progress_total INTEGER NOT NULL,
                    done INTEGER NOT NULL,
                    metrics TEXT,
                    last_snippet_id INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            doc_columns = {row[1] for row in conn.execute("PRAGMA table_info(naive_doc_tasks)")}
            if "metrics" not in doc_columns:
                conn.execute("ALTER TABLE naive_doc_tasks ADD COLUMN metrics TEXT")
            if "last_snippet_id" not in doc_columns:
                conn.execute(
                    "ALTER TABLE naive_doc_tasks ADD COLUMN last_snippet_id INTEGER NOT NULL DEFAULT 0"
                )
            if "keywords" not in doc_columns:
                conn.execute("ALTER TABLE naive_doc_tasks ADD COLUMN keywords TEXT NOT NULL")
            if "document_url" not in doc_columns:
                conn.execute("ALTER TABLE naive_doc_tasks ADD COLUMN document_url TEXT")
            if "demo" not in doc_columns:
                conn.execute("ALTER TABLE naive_doc_tasks ADD COLUMN demo INTEGER NOT NULL DEFAULT 0")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS naive_doc_snippets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    keyword TEXT NOT NULL,
                    snippet TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    line INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def create_doc_task(
        self,
        task_id: str,
        document_path: str,
        keywords: list[str],
        document_url: str | None = None,
        demo: bool = False,
    ) -> None:
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO naive_doc_tasks (
                    task_id, document_path, document_url, keywords, demo, status, progress_current, progress_total,
                    done, metrics, last_snippet_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    document_path,
                    document_url,
                    json.dumps(keywords),
                    1 if demo else 0,
                    "QUEUED",
                    0,
                    0,
                    0,
                    None,
                    0,
                    now,
                    now,
                ),
            )

    def claim_next_doc_task(self) -> NaiveDocTaskRow | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM naive_doc_tasks
                WHERE done = 0 AND status = 'QUEUED'
                ORDER BY created_at ASC
                LIMIT 1
                """
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                """
                UPDATE naive_doc_tasks
                SET status = 'RUNNING', updated_at = ?
                WHERE task_id = ?
                """,
                (_utc_now(), row["task_id"]),
            )
        return self.get_doc_task(row["task_id"])

    def get_doc_task(self, task_id: str) -> NaiveDocTaskRow | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM naive_doc_tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        if row is None:
            return None
        return NaiveDocTaskRow(
            task_id=row["task_id"],
            document_path=row["document_path"],
            document_url=row["document_url"],
            keywords=json.loads(row["keywords"]) if row["keywords"] else [],
            demo=bool(row["demo"]),
            status=row["status"],
            progress_current=row["progress_current"],
            progress_total=row["progress_total"],
            done=bool(row["done"]),
            metrics=json.loads(row["metrics"]) if row["metrics"] else None,
            last_snippet_id=row["last_snippet_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def update_doc_progress(
        self,
        task_id: str,
        *,
        progress_current: int,
        progress_total: int,
        done: bool,
        status: str,
        metrics: dict | None = None,
    ) -> None:
        metrics_json = json.dumps(metrics) if metrics is not None else None
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE naive_doc_tasks
                SET progress_current = ?, progress_total = ?, done = ?, status = ?,
                    metrics = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (
                    progress_current,
                    progress_total,
                    1 if done else 0,
                    status,
                    metrics_json,
                    _utc_now(),
                    task_id,
                ),
            )

    def append_doc_snippet(
        self,
        task_id: str,
        *,
        keyword: str,
        snippet: str,
        chunk_index: int,
        line: int,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO naive_doc_snippets (
                    task_id, keyword, snippet, chunk_index, line, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (task_id, keyword, snippet, chunk_index, line, _utc_now()),
            )

    def get_doc_snippets_since(self, task_id: str, last_id: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, keyword, snippet, chunk_index, line
                FROM naive_doc_snippets
                WHERE task_id = ? AND id > ?
                ORDER BY id ASC
                """,
                (task_id, last_id),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "keyword": row["keyword"],
                "snippet": row["snippet"],
                "chunk_index": row["chunk_index"],
                "line": row["line"],
            }
            for row in rows
        ]

    def mark_doc_snippets_delivered(self, task_id: str, last_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE naive_doc_tasks
                SET last_snippet_id = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (last_id, _utc_now(), task_id),
            )

    def get_max_snippet_id(self, task_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT MAX(id) AS max_id FROM naive_doc_snippets WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        return int(row["max_id"] or 0)

    def delete_doc_task(self, task_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM naive_doc_snippets WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM naive_doc_tasks WHERE task_id = ?", (task_id,))
