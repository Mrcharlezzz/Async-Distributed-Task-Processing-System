from __future__ import annotations

from typing import Any

from src.api.domain.models import StatusDTO
from src.api.infrastructure.mappers import to_status_dto


class DummyAsyncResult:
    def __init__(
        self,
        task_id: str,
        state: str,
        info: dict[str, Any] | None = None,
        result: Any | None = None,
        failed: bool = False,
        successful: bool = False,
    ):
        self.id = task_id
        self.state = state
        self.info = info or {}
        self.result = result
        self._failed = failed
        self._successful = successful

    def failed(self) -> bool:
        return self._failed

    def successful(self) -> bool:
        return self._successful


def test_to_status_dto_maps_failure_result():
    result = DummyAsyncResult(
        task_id="abc",
        state="FAILURE",
        info={"message": "boom", "progress": 0.3},
        failed=True,
        successful=False,
    )

    dto = to_status_dto(result)

    assert dto == StatusDTO(
        task_id="abc",
        state="FAILURE",
        progress=None,
        message="boom",
        result=None,
    )


def test_to_status_dto_maps_successful_result():
    result = DummyAsyncResult(
        task_id="xyz",
        state="SUCCESS",
        info={"progress": 0.75, "message": "almost there"},
        result={"result": "3"},
        failed=False,
        successful=True,
    )

    dto = to_status_dto(result)

    assert dto == StatusDTO(
        task_id="xyz",
        state="SUCCESS",
        progress=0.75,
        message="almost there",
        result= "3",
    )
