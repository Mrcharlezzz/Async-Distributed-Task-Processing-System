from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.domain.models import StatusDTO  # your Pydantic DTO
from src.api.application.services import ProgressService, TaskService
from src.setup.api_config import get_api_settings

router = APIRouter(tags=["tasks"])
logger = logging.getLogger(__name__)

# Instantiate services once (simple DI)
_settings = get_api_settings()
_task_service = TaskService()
_progress_service = ProgressService()

class EnqueueResponse(BaseModel):
    task_id: str = Field(..., description="Celery task id")


@router.get(
    "/calculate_pi",
    response_model=EnqueueResponse,
    summary="Start π calculation",
    description="Queues an asynchronous task to compute n digits of π. Returns the Celery task id.",
    responses={
        500: {
            "description": "Internal server error.",
        }
    },
)
def calculate_pi(n: int = Query(..., ge=1, le=_settings.MAX_DIGITS,description="Number of digits after decimal")):
    """
    Queues the `compute_pi` task.
    """
    try:
        task_id = _task_service.push_task("compute_pi", {"digits": n})
        return EnqueueResponse(task_id=task_id)
    except Exception as exc:
        logger.exception("Failed to enqueue task compute_pi: %s", exc)
        raise HTTPException(status_code=500)  # noqa: B904


@router.get(
    "/check_progress",
    response_model=StatusDTO,
    summary="Check task progress",
    description=(
        "Poll the status of a Celery task. Returns a JSON with keys:\n"
        "- state: 'PROGRESS' or 'FINISHED'\n"
        "- progress: 0..1 (float)\n"
        "- message: optional error message\n"
        "- result: final value or Null\n\n"
        "Example: {'state':'PROGRESS','progress':0.25,'message':Null, 'result':Null}\n"
    ),
    responses={
        500: {
            "description": "Internal server error.",
        }
    },
)
def check_progress(task_id: str = Query(..., description="Celery task id")):
    """
    Reads the Celery result backend for the given task id.
    """
    try:
        status = _progress_service.get_progress(task_id)
        return status
    except Exception as exc:
        logger.exception("Failed to get progress for task %s: %s", task_id, exc)
        raise HTTPException(status_code=500)  # noqa: B904
