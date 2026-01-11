from enum import Enum


class TaskState(str, Enum):
    """Lifecycle states for tasks."""
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
