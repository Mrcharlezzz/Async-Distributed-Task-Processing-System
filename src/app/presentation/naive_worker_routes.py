import logging
import time
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
import os
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from src.naive.compute_pi.storage import ComputePiStore
from src.naive.document_analysis.storage import DocumentAnalysisStore

router = APIRouter(prefix="/naive", tags=["naive"])
logger = logging.getLogger(__name__)
_CPU_MS_NAIVE: dict[str, float] = {}


class NaivePiRequest(BaseModel):
    digits: int = Field(..., ge=1, le=2000)
    task_id: str | None = None
    demo: bool = False


class NaiveDocRequest(BaseModel):
    document_path: str | None = Field(
        default=None, description="Local path to the document."
    )
    document_url: str | None = Field(
        default=None, description="Optional URL to download the document."
    )
    keywords: list[str] = Field(..., description="Keywords to search for.")
    task_id: str | None = None
    demo: bool = False


def _compute_store() -> ComputePiStore:
    store = ComputePiStore("/data/naive.sqlite")
    store.init_db()
    return store


def _doc_store() -> DocumentAnalysisStore:
    store = DocumentAnalysisStore("/data/naive.sqlite")
    store.init_db()
    return store


def _resolve_document_path(document_path: str | None, document_url: str | None) -> str | None:
    if document_url:
        parsed = urlparse(document_url)
        filename = os.path.basename(parsed.path) or "document.txt"
        return os.path.join("/data/books", filename)
    return document_path


@router.post("/calculate_pi")
def naive_calculate_pi(body: NaivePiRequest):
    store = _compute_store()
    task_id = body.task_id or uuid4().hex
    if store.get_task(task_id) is None:
        store.create_task(task_id, body.digits, demo=body.demo)
    return {"task_id": task_id}


@router.get("/check_progress")
def naive_check_progress(task_id: str = Query(..., description="Naive task id")):
    start_cpu = time.process_time()
    store = _compute_store()
    task = store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    percent = 0.0
    if task.progress_total:
        percent = task.progress_current / task.progress_total
    elapsed_ms = (time.process_time() - start_cpu) * 1000
    total_ms = _CPU_MS_NAIVE.get(task_id, 0.0) + elapsed_ms
    _CPU_MS_NAIVE[task_id] = total_ms
    return {
        "state": task.status,
        "progress": {
            "current": task.progress_current,
            "total": task.progress_total,
            "percentage": percent,
        },
        "metrics": task.metrics,
        "metadata": {
            "server_cpu_ms_naive": total_ms,
            "server_sent_ts": time.time(),
        },
    }


@router.get("/task_result")
def naive_task_result(task_id: str = Query(..., description="Naive task id")):
    start_cpu = time.process_time()
    store = _compute_store()
    task = store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    elapsed_ms = (time.process_time() - start_cpu) * 1000
    total_ms = _CPU_MS_NAIVE.get(task_id, 0.0) + elapsed_ms
    _CPU_MS_NAIVE[task_id] = total_ms
    response = {
        "task_id": task.task_id,
        "partial_result": task.result,
        "done": task.done,
        "metadata": {
            "server_cpu_ms_naive": total_ms,
            "server_sent_ts": time.time(),
        },
    }
    if task.done and task.demo:
        store.delete_task(task.task_id)
    return response


@router.post("/document-analysis")
def naive_document_analysis(body: NaiveDocRequest):
    store = _doc_store()
    task_id = body.task_id or uuid4().hex
    document_path = _resolve_document_path(body.document_path, body.document_url)
    if not document_path:
        raise HTTPException(status_code=400, detail="document_path or document_url is required")
    if store.get_doc_task(task_id) is None:
        store.create_doc_task(
            task_id,
            document_path,
            body.keywords,
            body.document_url,
            demo=body.demo,
        )
    return {"task_id": task_id}


@router.get("/document-analysis/status")
def naive_document_status(task_id: str = Query(..., description="Naive task id")):
    start_cpu = time.process_time()
    store = _doc_store()
    logger.info("Naive doc status requested", extra={"task_id": task_id})
    task = store.get_doc_task(task_id)
    if task is None:
        logger.warning("Naive doc status missing task", extra={"task_id": task_id})
        raise HTTPException(status_code=404, detail="Task not found")
    percent = 0.0
    if task.progress_total:
        percent = task.progress_current / task.progress_total
    elapsed_ms = (time.process_time() - start_cpu) * 1000
    total_ms = _CPU_MS_NAIVE.get(task_id, 0.0) + elapsed_ms
    _CPU_MS_NAIVE[task_id] = total_ms
    return {
        "state": task.status,
        "progress": {
            "current": task.progress_current,
            "total": task.progress_total,
            "percentage": percent,
        },
        "metrics": task.metrics,
        "metadata": {
            "server_cpu_ms_naive": total_ms,
            "server_sent_ts": time.time(),
        },
    }


@router.get("/document-analysis/snippets")
def naive_document_snippets(task_id: str = Query(...), after: int | None = None):
    start_cpu = time.process_time()
    store = _doc_store()
    logger.info("Naive doc snippets requested", extra={"task_id": task_id, "after": after})
    task = store.get_doc_task(task_id)
    if task is None:
        logger.warning("Naive doc snippets missing task", extra={"task_id": task_id})
        raise HTTPException(status_code=404, detail="Task not found")
    last_id = after if after is not None else task.last_snippet_id
    snippets = store.get_doc_snippets_since(task_id, last_id)
    logger.info(
        "Naive doc snippets fetched",
        extra={"task_id": task_id, "count": len(snippets), "last_id": last_id},
    )
    if snippets:
        store.mark_doc_snippets_delivered(task_id, snippets[-1]["id"])
    elapsed_ms = (time.process_time() - start_cpu) * 1000
    total_ms = _CPU_MS_NAIVE.get(task_id, 0.0) + elapsed_ms
    _CPU_MS_NAIVE[task_id] = total_ms
    response = {
        "snippets": snippets,
        "last_id": snippets[-1]["id"] if snippets else last_id,
        "metadata": {
            "server_cpu_ms_naive": total_ms,
            "server_sent_ts": time.time(),
        },
    }
    if task.done:
        max_id = store.get_max_snippet_id(task_id)
        if response["last_id"] >= max_id and task.demo:
            store.delete_doc_task(task_id)
    return response
