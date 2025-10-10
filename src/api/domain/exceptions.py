class TaskNotFoundError(Exception):
    """Raised when a task identifier does not exist in the task backend."""
    def __init__(self, task_id: str) -> None:
        super().__init__(f"Task with id '{task_id}' was not found.")
        self.task_id = task_id