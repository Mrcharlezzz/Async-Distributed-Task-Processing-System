import bisect
import itertools
import logging
import os
import random
import re
import time
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
    """Emit a snippet result chunk with its keyword and location."""
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
    """Resolve a local path for a document or infer it from the URL."""
    if document_url:
        parsed = urlparse(document_url)
        filename = os.path.basename(parsed.path) or "document.txt"
        return os.path.join(DEFAULT_DOWNLOAD_DIR, filename)
    return document_path


def _ensure_document(document_path: str, document_url: str | None) -> None:
    """Download the document if a URL is provided and the file is missing."""
    if not document_url:
        return
    if os.path.exists(document_path):
        return
    directory = os.path.dirname(document_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    urllib.request.urlretrieve(document_url, document_path)


def _report_failed(reporter: TaskReporter, message: str) -> dict:
    """Emit a failed status and return an error payload."""
    logger.error("Document analysis failed: %s", message)
    status = TaskStatus(
        state=TaskState.FAILED,
        progress=TaskProgress(current=0, total=0, percentage=0.0),
        message=message,
        metrics={"snippets_emitted": 0},
    )
    reporter.report_status(status)
    return {"error": message}


def _report_running_status(
    reporter: TaskReporter,
    *,
    bytes_read: int,
    total_bytes: int,
    snippets_emitted: int,
) -> None:
    """Report progress based on bytes read and snippets emitted."""
    progress = bytes_read / total_bytes if total_bytes else 1.0
    reporter.report_status(
        TaskStatus(
            state=TaskState.RUNNING,
            progress=TaskProgress(
                current=bytes_read,
                total=total_bytes,
                percentage=progress,
            ),
            metrics={
                "snippets_emitted": snippets_emitted,
            },
        )
    )


@celery_app.task(name="document_analysis", bind=True)
def document_analysis(self, payload: dict) -> dict:
    """Scan a document for keywords and stream snippet hits."""
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
    total_snippets_emitted = 0
    chunk_index = 0
    line_number = 1

    reporter.report_status(
        TaskStatus(
            state=TaskState.RUNNING,
            progress=TaskProgress(current=0, total=total_bytes, percentage=0.0),
            message="started",
            metrics={
                "snippets_emitted": 0,
            },
        )
    )

    with reporter.report_result_chunk(batch_size=1) as chunks:
        with open(document_path, "rb") as handle:
            while True:
                # Read a variable number of lines to simulate uneven workload.
                lines_to_read = random.randint(MIN_LINES_PER_CHUNK, MAX_LINES_PER_CHUNK)
                chunk_start = handle.tell()
                lines = list(itertools.islice(handle, lines_to_read))
                if not lines:
                    break

                # Decode once per chunk, then search in-memory.
                text_lines = [line.decode("utf-8", errors="ignore") for line in lines]
                chunk_text = "".join(text_lines)
                line_offsets = list(
                    itertools.accumulate((len(line) for line in text_lines), initial=0)
                )
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
                    # Add jitter after each snippet to show uneven streaming.
                    time.sleep(random.uniform(0.1, 0.5))  # Simulate processing delay
                    bytes_read = min(chunk_start + match.start(), total_bytes)
                    _report_running_status(
                        reporter,
                        bytes_read=bytes_read,
                        total_bytes=total_bytes,
                        snippets_emitted=total_snippets_emitted,
                    )

                if snippets_emitted == 0:
                    # Even with no hits, advance progress to avoid stalling.
                    _report_running_status(
                        reporter,
                        bytes_read=handle.tell(),
                        total_bytes=total_bytes,
                        snippets_emitted=total_snippets_emitted,
                    )

                chunk_index += 1
                line_number += len(lines)

    reporter.report_status(
        TaskStatus(
            state=TaskState.COMPLETED,
            progress=TaskProgress(current=total_bytes, total=total_bytes, percentage=1.0),
            message="completed",
            metrics={
                "snippets_emitted": total_snippets_emitted,
            },
        )
    )
    # Final summary result is stored once for retrieval.
    reporter.report_result(
        {
            "task_id": self.request.id,
            "chunks_scanned": chunk_index,
            "snippets_emitted": total_snippets_emitted,
        }
    )
    return {"chunks_scanned": chunk_index, "snippets_emitted": total_snippets_emitted}
