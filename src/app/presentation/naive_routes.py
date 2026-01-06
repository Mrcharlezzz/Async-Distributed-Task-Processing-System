from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.naive.storage import NaiveStore

router = APIRouter(prefix="/naive", tags=["naive"])


class NaivePiRequest(BaseModel):
    digits: int = Field(..., ge=1, le=2000)
    task_id: str | None = None


def _store() -> NaiveStore:
    store = NaiveStore("/data/naive.sqlite")
    store.init_db()
    return store


@router.post("/calculate_pi")
def naive_calculate_pi(body: NaivePiRequest):
    store = _store()
    task_id = body.task_id or uuid4().hex
    if store.get_task(task_id) is None:
        store.create_task(task_id, body.digits)
    return {"task_id": task_id}


@router.get("/check_progress")
def naive_check_progress(task_id: str = Query(..., description="Naive task id")):
    store = _store()
    task = store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    percent = 0.0
    if task.progress_total:
        percent = task.progress_current / task.progress_total
    return {
        "state": task.status,
        "progress": {
            "current": task.progress_current,
            "total": task.progress_total,
            "percentage": percent,
        },
        "metrics": task.metrics,
    }


@router.get("/task_result")
def naive_task_result(task_id: str = Query(..., description="Naive task id")):
    store = _store()
    task = store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "task_id": task.task_id,
        "partial_result": task.result,
        "done": task.done,
    }
