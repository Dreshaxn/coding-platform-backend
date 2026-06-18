# SocialCode Backend

FastAPI backend for SocialCode, a competitive programming platform where users
solve coding challenges, submit code, and compete in real-time coding races.

The backend provides authentication, problem management, submissions, race
workflows, Redis-backed real-time updates, and a Docker-based online judge for
running untrusted user code.

## Features

- JWT-based authentication and protected user routes
- Problem, difficulty, category, language, template, and test case models
- Code submissions with asynchronous judging
- Redis-backed submission queue, cache, and pub/sub status updates
- WebSocket support for live submission and race updates
- Multiplayer coding race APIs for joining, readying, starting, submitting, and
  syncing race progress
- Docker-based execution engine for Python, Java, and C submissions
- Alembic migrations for PostgreSQL schema changes
- Pytest coverage for routes, services, races, submissions, cache fallback, and
  worker behavior

## Tech Stack

- **API:** FastAPI
- **Database:** PostgreSQL, SQLAlchemy, Alembic
- **Cache/Queue/PubSub:** Redis
- **Auth:** JWT, passlib, python-jose
- **Worker:** Redis queue consumer
- **Judge:** Docker containers with CPU, memory, process, timeout, and network
  restrictions
- **Tests:** pytest

## Project Structure

```text
app/
  api/              FastAPI routers and dependencies
  cache/            Redis cache, queue, and pub/sub helpers
  core/             App settings and security helpers
  db/               SQLAlchemy session and metadata setup
  models/           SQLAlchemy ORM models
  repositories/     Database access layer
  schemas/          Pydantic request/response schemas
  services/         Business logic
worker/
  config.py         Supported languages and execution limits
  executor.py       Docker-based code execution engine
  judge_worker.py   Redis queue worker for judging submissions
alembic/
  versions/         Database migrations
tests/              Pytest suite
```

## Prerequisites

- Python 3.10+
- PostgreSQL
- Redis
- Docker

Docker is required for the online judge because submissions are executed inside
isolated containers.

## Environment Variables

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/socialcode
SECRET_KEY=replace-with-a-long-random-secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REDIS_URL=redis://localhost:6379/0
WS_HEARTBEAT_INTERVAL=30
CACHE_DEFAULT_TTL=300
```

Do not commit real secrets. The repository ignores `.env` and `.env.*`.

## Setup

Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

If your environment does not already include `pydantic-settings`, install it:

```bash
pip install pydantic-settings
```

Apply database migrations:

```bash
alembic upgrade head
```

Run the API:

```bash
uvicorn app.main:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

FastAPI docs are available at:

```text
http://127.0.0.1:8000/docs
```

## Running the Judge Worker

Start Redis and Docker first, then run:

```bash
python -m worker.judge_worker
```

To run a named worker:

```bash
python -m worker.judge_worker --worker-id worker-1
```

The worker blocks on the Redis `judge:queue` list, loads pending submissions
from PostgreSQL, executes them in Docker, stores the verdict, and publishes
status updates through Redis pub/sub.

## Running Tests

```bash
pytest
```

For quieter output:

```bash
pytest -q
```

## Main API Areas

Authentication:

- `POST /auth/register`
- `POST /auth/login`
- authenticated user lookup routes

Problems:

- `GET /problems`
- `GET /problems/{problem_id}`
- `POST /problems`
- `POST /problems/{problem_id}/solve`
- `GET /problems/{problem_id}/template`

Submissions:

- `POST /submissions`
- `GET /submissions`
- `GET /submissions/{submission_id}`

Races:

- `POST /races`
- `GET /races/{race_id}`
- `POST /races/{race_id}/join`
- `POST /races/{race_id}/ready`
- `POST /races/{race_id}/start`
- `POST /races/{race_id}/submissions`
- `GET /races/{race_id}/progress`

WebSockets:

- live submission status updates
- race state synchronization

See `/docs` for the current generated OpenAPI schema.

## Online Judge Overview

Submission flow:

1. A user submits code through the API.
2. The API stores the submission as pending.
3. The submission id is pushed into Redis.
4. The judge worker pops the submission id from Redis.
5. The worker loads the problem, language, and test cases.
6. Test cases and problem metadata may be served from Redis cache.
7. The Docker executor runs the submitted code against the test cases.
8. The worker stores the verdict and per-test results.
9. Redis pub/sub broadcasts status updates to WebSocket clients.

Supported judge languages:

- Python 3.12
- Java 21
- C with GCC 13

Execution protections include:

- no network access
- CPU limits
- memory limits
- process limits
- open file limits
- execution timeouts
- output truncation
- dropped Linux capabilities

## Development Notes

- The real application entry point is `app.main:app`.
- The root `main.py` is a minimal FastAPI app and does not include the project
  routers.
- `DATABASE_URL`, `SECRET_KEY`, and `REDIS_URL` are required at import time.
- The current database session code appends `?sslmode=require` to
  `DATABASE_URL`; local PostgreSQL setups may need this adjusted if SSL is not
  enabled.

## Common Commands

```bash
# install dependencies
pip install -r requirements.txt

# run migrations
alembic upgrade head

# start API
uvicorn app.main:app --reload

# start judge worker
python -m worker.judge_worker

# run tests
pytest -q
```
