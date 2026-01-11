from enum import Enum


class TaskType(str, Enum):
    """Supported task types."""
    COMPUTE_PI = "compute_pi"
    DOCUMENT_ANALYSIS = "document_analysis"
