# PostTagger-Reimagined-Test-Task

Test Task project for JetBrains internship application.

## Table of Contents
- [Overview](#overview)
- [Structure](#structure)
- [Prerequisites](#prerequisites)
- [Configuration](#configuration)
- [Running With Docker Compose](#running-with-docker-compose)
- [Available Services & Endpoints](#available-services--endpoints)
- [Task Workflow](#task-workflow)

## Overview
This project exposes an HTTP API that allows clients to enqueue long-running jobs (e.g., computing π) and poll for their status. Celery is used as the task queue, Redis serves as broker/backend, and FastAPI provides the HTTP layer. The service is designed with a scalable architecture, allowing new background tasks to be easily added.

## Structure
- **FastAPI (src/api/presentation)** — HTTP routing and request handling
- **Application services (src/api/application)** — Orchestrate task creation and status queries
- **Domain (src/api/domain)** — Shared models, repositories, and exceptions
- **Infrastructure (src/api/infrastructure)** — Celery integration and mappers
- **Worker (src/worker/tasks.py)** — Celery task implementations
- **Config (src/setup)** - Configuration files

## Prerequisites
- Docker for containerized setup

## Configuration
Defaults for the API name/version, Redis URL, max digits, and worker pacing are baked into
the settings classes (`src/setup`). You can still override any of them by creating a `.env`
file with the relevant variables (see `src/setup/*.py` for names).


## Running With Docker Compose
```bash
docker compose up --build
```
Services started:
- `api` — FastAPI application on `http://localhost:8000`
- `worker` — Celery worker
- `redis` — Redis broker/backend

## Available Services & Endpoints
### API
- `POST /calculate_pi` — enqueue π computation (JSON body: `{"n": <digits>}`)
- `GET /check_progress?task_id=<id>` — retrieve task progress

### Worker
- Task: `compute_pi` defined in `src/worker/tasks.py`

## Task Workflow
1. Client calls `POST /calculate_pi` with `{"n": <digits>}`.
2. API enqueues `compute_pi` via Celery.
3. Worker updates progress using `update_state` and ultimately stores the result.
4. Client polls `/check_progress` until `state` is `SUCCESS`.
