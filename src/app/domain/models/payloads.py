from pydantic import BaseModel, Field


class TaskPayload(BaseModel):
    """Marker/base class for task payloads."""

    pass


class DocumentAnalysisPayload(TaskPayload):
    """Payload for document analysis tasks."""
    document_path: str | None = Field(
        default=None,
        description="Local path to the document to analyze.",
    )
    document_url: str | None = Field(
        default=None,
        description="Optional URL to download the document before processing.",
    )
    keywords: list[str] = Field(
        description="Keywords to search for (case-insensitive substring match)."
    )


class ComputePiPayload(TaskPayload):
    """Payload for computing digits of pi."""
    digits: int = Field(description="Number of digits to compute.")
