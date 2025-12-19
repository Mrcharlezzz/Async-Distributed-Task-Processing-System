import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.application.services import ProgressService, TaskService
from src.api.domain.models import DocumentAnalysisPayload
from src.api.domain.exceptions import TaskNotFoundError
from src.api.domain.models.task import Task
from src.api.domain.models.task_status import TaskStatus
from src.setup.api_config import get_api_settings

router = APIRouter(tags=["tasks"])
logger = logging.getLogger(__name__)


_settings = get_api_settings()

_task_service = TaskService()
_progress_service = ProgressService()


def get_task_service() -> TaskService:
    return TaskService()

class EnqueueResponse(BaseModel):
    task_id: str = Field(..., description="Celery task id")

# EnqueueResponse is used for legacy /calculate_pi endpoint returning only task id.

class CalculatePiRequest(BaseModel):
    n: int = Field(..., ge=1, le=_settings.MAX_DIGITS, description="Number of digits after decimal")


@router.post(
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
async def calculate_pi(body: CalculatePiRequest):
    """
    Queues the `compute_pi` task.
    """
    try:
        task_id = await _task_service.push_task("compute_pi", {"digits": body.n})
        return EnqueueResponse(task_id=task_id)
    except Exception as exc:
        logger.exception("Failed to enqueue task compute_pi: %s", exc)
        raise HTTPException(status_code=500)  # noqa: B904


@router.get(
    "/check_progress",
    response_model=TaskStatus,
    summary="Check task progress",
    description=(
        "Poll the status of a Celery task. Returns a JSON with keys:\n"
        "- state: 'QUEUED', 'RUNNING', 'COMPLETED', 'FAILED', or 'CANCELLED'\n"
        "- progress: object with current/total/percentage/phase (optional)\n"
        "- message: optional error message\n"
        "\nExample: {'state':'RUNNING','progress':{'percentage':0.25},'message':Null}\n"
    ),
    responses={
        404: {
            "description": "Task id not found.",
        },
        500: {
            "description": "Internal server error.",
        },
    },
)
async def check_progress(task_id: str = Query(..., description="Celery task id")):
    """
    Reads the Celery result backend for the given task id.
    """
    try:
        status = await _progress_service.get_progress(task_id)
        return status
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to get progress for task %s: %s", task_id, exc)
        raise HTTPException(status_code=500)  # noqa: B904


@router.post(
    "/tasks/document-analysis",
    response_model=Task,
    summary="Create document analysis task",
)
async def create_doc_task(
    body: DocumentAnalysisPayload, svc: TaskService = Depends(get_task_service)
):
    """
    Enqueue a document analysis task with a typed payload.
    """
    task = await svc.create_task(body)
    return task
