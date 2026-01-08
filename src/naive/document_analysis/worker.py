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
MAX_SNIPPETS_PER_CHUNK = 20
DEFAULT_DOWNLOAD_DIR = "/data/books"


def _eta_seconds(start_time: float, processed_bytes: int, total_bytes: int) -> float:
    elapsed = time.monotonic() - start_time
    if processed_bytes <= 0 or elapsed <= 0 or total_bytes <= 0:
        return 0.0
    rate = processed_bytes / elapsed
    remaining = max(total_bytes - processed_bytes, 0)
    return remaining / rate if rate > 0 else 0.0


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


def _mark_failed(store: DocumentAnalysisStore, task_id: str) -> None:
    store.update_doc_progress(
        task_id,
        progress_current=0,
        progress_total=0,
        done=True,
        status="FAILED",
        metrics={"eta_seconds": 0.0, "snippets_emitted": 0, "words_processed": 0},
    )


def main() -> None:
    db_path = "/data/naive.sqlite"
    idle_sleep = 0.2

    store = DocumentAnalysisStore(db_path)
    store.init_db()

    while True:
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

        with open(document_path, "r", encoding="utf-8", errors="ignore") as handle:
            total_bytes = os.path.getsize(document_path)
            start_time = time.monotonic()
            snippet_count = 0
            words_processed = 0
            chunk_index = 0
            line_number = 1

            store.update_doc_progress(
                task.task_id,
                progress_current=0,
                progress_total=total_bytes,
                done=False,
                status="RUNNING",
                metrics={
                    "eta_seconds": 0.0,
                    "snippets_emitted": 0,
                    "words_processed": 0,
                },
            )

            pattern = re.compile(
                "|".join(re.escape(k) for k in task.keywords), re.IGNORECASE
            )

            while True:
                lines_to_read = random.randint(MIN_LINES_PER_CHUNK, MAX_LINES_PER_CHUNK)
                lines = list(itertools.islice(handle, lines_to_read))
                if not lines:
                    break

                chunk_text = "".join(lines)
                line_offsets = list(itertools.accumulate((len(line) for line in lines), initial=0))
                words_processed += len(chunk_text.split())

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
                    store.append_doc_snippet(
                        task.task_id,
                        keyword=match.group(0),
                        snippet=snippet,
                        chunk_index=chunk_index,
                        line=snippet_line,
                    )
                    snippets_emitted += 1
                    snippet_count += 1

                bytes_read = handle.tell()
                eta = _eta_seconds(start_time, bytes_read, total_bytes)
                store.update_doc_progress(
                    task.task_id,
                    progress_current=bytes_read,
                    progress_total=total_bytes,
                    done=False,
                    status="RUNNING",
                    metrics={
                        "eta_seconds": eta,
                        "snippets_emitted": snippet_count,
                        "words_processed": words_processed,
                    },
                )

                chunk_index += 1
                line_number += len(lines)

            store.update_doc_progress(
                task.task_id,
                progress_current=total_bytes,
                progress_total=total_bytes,
                done=True,
                status="COMPLETED",
                metrics={
                    "eta_seconds": 0.0,
                    "snippets_emitted": snippet_count,
                    "words_processed": words_processed,
                },
            )


if __name__ == "__main__":
    main()
