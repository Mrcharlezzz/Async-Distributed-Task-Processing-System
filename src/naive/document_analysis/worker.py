import bisect
import itertools
import os
import random
import re
import time
import urllib.request
from urllib.parse import urlparse

from src.naive.document_analysis.storage import DocumentAnalysisStore

MIN_LINES_PER_CHUNK = 50
MAX_LINES_PER_CHUNK = 300
SNIPPET_RADIUS = 30
MAX_SNIPPETS_PER_CHUNK = 2000
DEFAULT_DOWNLOAD_DIR = "/data/books"


def _resolve_document_path(document_path: str | None, document_url: str | None) -> str | None:
    """Resolve a local path for the document or infer it from the URL."""
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


def _mark_failed(store: DocumentAnalysisStore, task_id: str) -> None:
    """Persist a failed status for a document analysis task."""
    store.update_doc_progress(
        task_id,
        progress_current=0,
        progress_total=0,
        done=True,
        status="FAILED",
        metrics={"snippets_emitted": 0},
    )


def main() -> None:
    """Run the naive document analysis worker loop against the SQLite queue."""
    db_path = "/data/naive.sqlite"
    idle_sleep = 0.2

    store = DocumentAnalysisStore(db_path)
    store.init_db()

    while True:
        # Poll for the next queued task; sleep briefly when idle.
        task = store.claim_next_doc_task()
        if task is None:
            time.sleep(idle_sleep)
            continue

        document_path = _resolve_document_path(task.document_path, task.document_url)
        if not document_path:
            _mark_failed(store, task.task_id)
            continue

        try:
            _ensure_document(document_path, task.document_url)
        except Exception:
            _mark_failed(store, task.task_id)
            continue
        if not os.path.exists(document_path):
            _mark_failed(store, task.task_id)
            continue

        with open(document_path, "rb") as handle:
            total_bytes = os.path.getsize(document_path)
            snippet_count = 0
            chunk_index = 0
            line_number = 1

            # Initial running status so the client sees task start immediately.
            store.update_doc_progress(
                task.task_id,
                progress_current=0,
                progress_total=total_bytes,
                done=False,
                status="RUNNING",
                metrics={
                    "snippets_emitted": 0,
                },
            )

            pattern = re.compile(
                "|".join(re.escape(k) for k in task.keywords), re.IGNORECASE
            )

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
                    pos = match.start()
                    snippet_start = max(pos - SNIPPET_RADIUS, 0)
                    snippet_end = min(pos + len(match.group(0)) + SNIPPET_RADIUS, len(chunk_text))
                    snippet = chunk_text[snippet_start:snippet_end]
                    line_offset = bisect.bisect_right(line_offsets, pos) - 1
                    snippet_line = line_number + line_offset
                    # Persist each snippet for the polling client to fetch.
                    store.append_doc_snippet(
                        task.task_id,
                        keyword=match.group(0),
                        snippet=snippet,
                        chunk_index=chunk_index,
                        line=snippet_line,
                    )
                    snippets_emitted += 1
                    snippet_count += 1
                    # Add jitter after each snippet to show uneven streaming.
                    time.sleep(random.uniform(0.1, 0.5))  # Simulate processing delay
                    bytes_read = min(chunk_start + match.start(), total_bytes)
                    # Update progress alongside snippet emission.
                    store.update_doc_progress(
                        task.task_id,
                        progress_current=bytes_read,
                        progress_total=total_bytes,
                        done=False,
                        status="RUNNING",
                        metrics={
                            "snippets_emitted": snippet_count,
                        },
                    )

                if snippets_emitted == 0:
                    # Even with no hits, advance progress to avoid stalling.
                    bytes_read = handle.tell()
                    store.update_doc_progress(
                        task.task_id,
                        progress_current=bytes_read,
                        progress_total=total_bytes,
                        done=False,
                    status="RUNNING",
                    metrics={
                        "snippets_emitted": snippet_count,
                    },
                )

                chunk_index += 1
                line_number += len(lines)

            # Mark completion after scanning the full file.
            store.update_doc_progress(
                task.task_id,
                progress_current=total_bytes,
                progress_total=total_bytes,
                done=True,
                status="COMPLETED",
                metrics={
                    "snippets_emitted": snippet_count,
                },
            )


if __name__ == "__main__":
    main()
