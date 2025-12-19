from pydantic import BaseModel


class TaskPayload(BaseModel):
    """Marker/base class for task payloads."""

    pass


class DocumentAnalysisPayload(TaskPayload):
    document_ids: list[str]
    run_ocr: bool = True
    language: str = "eng"
