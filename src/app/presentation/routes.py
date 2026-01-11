import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.app.application.services import TaskService
from src.app.domain.models import (
    ComputePiPayload,
    DocumentAnalysisPayload,
    TaskResult,
    TaskType,
)
from src.app.domain.exceptions import TaskNotFoundError
from src.app.domain.models.task import Task
from src.app.domain.models.task_status import TaskStatus
from src.setup.api_config import ApiSettings

router = APIRouter(tags=["tasks"])
logger = logging.getLogger(__name__)


_settings = ApiSettings()

def get_task_service() -> TaskService:
    return TaskService()

class CalculatePiRequest(BaseModel):
    n: int = Field(..., ge=1, le=_settings.MAX_DIGITS, description="Number of digits after decimal")


@router.post(
    "/calculate_pi",
    response_model=Task,
    summary="Start π calculation",
    description="Queues an asynchronous task to compute n digits of π.",
    responses={
        500: {
            "description": "Internal server error.",
        }
    },
)
async def calculate_pi(body: CalculatePiRequest, svc: TaskService = Depends(get_task_service)):
    """
    Queues the `compute_pi` task.
    """
    try:
        payload = ComputePiPayload(digits=body.n)
        task = await svc.create_task(TaskType.COMPUTE_PI, payload)
        return task
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
async def check_progress(
    task_id: str = Query(..., description="Celery task id"),
    svc: TaskService = Depends(get_task_service),
):
    """
    Reads the Celery result backend for the given task id.
    """
    try:
        status = await svc.get_status(task_id)
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
    task = await svc.create_task(TaskType.DOCUMENT_ANALYSIS, body)
    return task


@router.get(
    "/task_result",
    response_model=TaskResult,
    summary="Fetch task result",
    description="Retrieve the result payload for a task id, if available.",
    responses={
        404: {
            "description": "Task id not found.",
        },
        500: {
            "description": "Internal server error.",
        },
    },
)
async def get_task_result(
    task_id: str = Query(..., description="Celery task id"),
    svc: TaskService = Depends(get_task_service),
):
    """
    Reads the Celery result backend for the given task id.
    """
    try:
        result = await svc.get_result(task_id)
        return result
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to get result for task %s: %s", task_id, exc)
        raise HTTPException(status_code=500)  # noqa: B904
