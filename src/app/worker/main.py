import os

from src.setup.stream_config import configure_stream_publisher
from src.app.infrastructure.celery.app import celery_app


def main() -> None:
    log_level = os.getenv("LOG_LEVEL", "INFO")
    concurrency = os.getenv("CELERY_CONCURRENCY", "2")
    queues = os.getenv("CELERY_QUEUES", "celery,doc-tasks")
    configure_stream_publisher()
    celery_app.autodiscover_tasks(["src.app.worker"])
    celery_app.worker_main(
        [
            "worker",
            "-l",
            log_level,
            "--concurrency",
            concurrency,
            "-Q",
            queues,
        ]
    )


if __name__ == "__main__":
    main()
