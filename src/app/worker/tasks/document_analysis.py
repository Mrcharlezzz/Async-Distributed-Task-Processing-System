import itertools
import os
import random
import time
import bisect
import re
import logging
import urllib.request
from urllib.parse import urlparse

from src.app.domain.models.task_progress import TaskProgress
from src.app.domain.models.task_state import TaskState
from src.app.domain.models.task_status import TaskStatus
from src.app.infrastructure.celery.app import celery_app
from src.app.worker.reporter import TaskReporter

MIN_LINES_PER_CHUNK = 50
MAX_LINES_PER_CHUNK = 300
SNIPPET_RADIUS = 30
MAX_SNIPPETS_PER_CHUNK = 2000
DEFAULT_DOWNLOAD_DIR = "/data/books"

logger = logging.getLogger(__name__)


def _eta_seconds(start_time: float, processed_bytes: int, total_bytes: int) -> float:
    elapsed = time.monotonic() - start_time
    if processed_bytes <= 0 or elapsed <= 0 or total_bytes <= 0:
        return 0.0
    rate = processed_bytes / elapsed
    remaining = max(total_bytes - processed_bytes, 0)
    return remaining / rate if rate > 0 else 0.0


def _emit_snippet(
    chunks: TaskReporter,
    *,
    match: re.Match[str],
    chunk_text: str,
    line_offsets: list[int],
    line_number: int,
    chunk_index: int,
    document_path: str,
) -> None:
    pos = match.start()
    snippet_start = max(pos - SNIPPET_RADIUS, 0)
    snippet_end = min(pos + len(match.group(0)) + SNIPPET_RADIUS, len(chunk_text))
    snippet = chunk_text[snippet_start:snippet_end]
    line_offset = bisect.bisect_right(line_offsets, pos) - 1
    snippet_line = line_number + line_offset
    chunks.emit(
        {
            "type": "snippet_found",
            "keyword": match.group(0),
            "snippet": snippet,
            "location": {
                "chunk_index": chunk_index,
                "line": snippet_line,
            },
            "file": document_path,
        }
    )


def _resolve_document_path(document_path: str | None, document_url: str | None) -> str | None:
    if document_url:
        parsed = urlparse(document_url)
        filename = os.path.basename(parsed.path) or "document.txt"
        return os.path.join(DEFAULT_DOWNLOAD_DIR, filename)
    return document_path


def _ensure_document(document_path: str, document_url: str | None) -> None:
    if not document_url:
        return
    if os.path.exists(document_path):
        return
    directory = os.path.dirname(document_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    urllib.request.urlretrieve(document_url, document_path)


def _report_failed(reporter: TaskReporter, message: str) -> dict:
    logger.error("Document analysis failed: %s", message)
    status = TaskStatus(
        state=TaskState.FAILED,
        progress=TaskProgress(current=0, total=0, percentage=0.0),
        message=message,
        metrics={"eta_seconds": 0.0, "snippets_emitted": 0, "words_processed": 0},
    )
    reporter.report_status(status)
    return {"error": message}


def _report_running_status(
    reporter: TaskReporter,
    *,
    bytes_read: int,
    total_bytes: int,
    snippets_emitted: int,
    words_processed: int,
    start_time: float,
) -> None:
    progress = bytes_read / total_bytes if total_bytes else 1.0
    eta = _eta_seconds(start_time, bytes_read, total_bytes)
    reporter.report_status(
        TaskStatus(
            state=TaskState.RUNNING,
            progress=TaskProgress(
                current=bytes_read,
                total=total_bytes,
                percentage=progress,
            ),
            metrics={
                "eta_seconds": eta,
                "snippets_emitted": snippets_emitted,
                "words_processed": words_processed,
            },
        )
    )


@celery_app.task(name="document_analysis", bind=True)
def document_analysis(self, payload: dict) -> dict:
    reporter = TaskReporter(self.request.id)
    payload_data = payload.get("payload") or {}
    document_path = payload_data.get("document_path")
    document_url = payload_data.get("document_url")
    keywords = payload_data.get("keywords") or []

    document_path = _resolve_document_path(document_path, document_url)

    if not document_path:
        return _report_failed(reporter, "document_path or document_url is required")

    if not keywords:
        return _report_failed(reporter, "keywords are required")

    try:
        _ensure_document(document_path, document_url)
    except Exception as exc:
        return _report_failed(reporter, f"failed to download document: {exc}")

    if not os.path.exists(document_path):
        return _report_failed(reporter, f"document_path not found: {document_path}")

    total_bytes = os.path.getsize(document_path)
    pattern = re.compile("|".join(re.escape(keyword) for keyword in keywords), re.IGNORECASE)
    start_time = time.monotonic()
    total_snippets_emitted = 0
    words_processed = 0
    chunk_index = 0
    line_number = 1

    reporter.report_status(
        TaskStatus(
            state=TaskState.RUNNING,
            progress=TaskProgress(current=0, total=total_bytes, percentage=0.0),
            message="started",
            metrics={
                "eta_seconds": 0.0,
                "snippets_emitted": 0,
                "words_processed": 0,
            },
        )
    )

    with reporter.report_result_chunk(batch_size=1) as chunks:
        with open(document_path, "rb") as handle:
            while True:
                lines_to_read = random.randint(MIN_LINES_PER_CHUNK, MAX_LINES_PER_CHUNK)
                lines = list(itertools.islice(handle, lines_to_read))
                if not lines:
                    break

                text_lines = [line.decode("utf-8", errors="ignore") for line in lines]
                chunk_text = "".join(text_lines)
                line_offsets = list(
                    itertools.accumulate((len(line) for line in text_lines), initial=0)
                )
                words_processed += len(chunk_text.split())

                snippets_emitted = 0
                for match in pattern.finditer(chunk_text):
                    if snippets_emitted >= MAX_SNIPPETS_PER_CHUNK:
                        break
                    _emit_snippet(
                        chunks,
                        match=match,
                        chunk_text=chunk_text,
                        line_offsets=line_offsets,
                        line_number=line_number,
                        chunk_index=chunk_index,
                        document_path=document_path,
                    )
                    snippets_emitted += 1
                    total_snippets_emitted += 1
                    time.sleep(random.uniform(0.1, 0.5))  # Simulate processing delay
                    _report_running_status(
                        reporter,
                        bytes_read=handle.tell(),
                        total_bytes=total_bytes,
                        snippets_emitted=total_snippets_emitted,
                        words_processed=words_processed,
                        start_time=start_time,
                    )

                if snippets_emitted == 0:
                    _report_running_status(
                        reporter,
                        bytes_read=handle.tell(),
                        total_bytes=total_bytes,
                        snippets_emitted=total_snippets_emitted,
                        words_processed=words_processed,
                        start_time=start_time,
                    )

                chunk_index += 1
                line_number += len(lines)

    reporter.report_status(
        TaskStatus(
            state=TaskState.COMPLETED,
            progress=TaskProgress(current=total_bytes, total=total_bytes, percentage=1.0),
            message="completed",
            metrics={
                "eta_seconds": 0.0,
                "snippets_emitted": total_snippets_emitted,
                "words_processed": words_processed,
            },
        )
    )
    reporter.report_result(
        {
            "task_id": self.request.id,
            "chunks_scanned": chunk_index,
            "snippets_emitted": total_snippets_emitted,
        }
    )
    return {"chunks_scanned": chunk_index, "snippets_emitted": total_snippets_emitted}
