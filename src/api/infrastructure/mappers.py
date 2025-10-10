from celery.result import AsyncResult
from pydantic import ValidationError

from src.api.domain.exceptions import TaskNotFoundError
from src.api.domain.models import StatusDTO


def to_status_dto(async_result : AsyncResult) -> StatusDTO:
    info = async_result.info or {}

    if async_result.state == "PENDING":
        raise TaskNotFoundError(async_result.id)

    try:
        if async_result.failed():
            return StatusDTO(
                task_id=async_result.id,
                state="FAILURE",
                progress=None,
                message=info.get("message"),
                result=None,
            )

        return StatusDTO(
            task_id=async_result.id,
            state=async_result.state,
            progress=info.get("progress"),
            message=info.get("message"),
            result = async_result.result["result"]
        )

    except ValidationError as e:
        # fallback: mark as failure with error message
        return StatusDTO(
            task_id=async_result.id,
            state="FAILURE",
            progress=None,
            message=f"Mapping error: {e.errors()}",
            result=None,
        )

"""
TODO


implement task missing logic

check not found task


check not found task

try to decouple worker import from docker compose

"""