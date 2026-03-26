# Dialearn Backend

Backend for Dialearn, a conversational AI learning competency assessment platform built with FastAPI, hexagonal architecture, PostgreSQL, Valkey, Alembic, SQLAlchemy async ORM, and dependency-injector.

## Product Focus

Dialearn helps evaluate learning competency through interactive AI-driven assessment flows.

- students answer open-ended questions in a conversational interface
- AI generates contextual follow-up questions to probe depth of understanding
- instructors manage assessments, materials, and evaluation criteria
- reports highlight strengths, weaknesses, and learning trends

## Built-In Modules

- `user`: account and identity management
- `auth`: JWT cookie login, refresh rotation, logout, and Valkey-backed token storage
- `file`: file metadata management with status transitions

These modules are currently part of the backend baseline and can support or be extended for Dialearn-specific domains.

## Stack

- FastAPI
- SQLAlchemy 2.x async ORM
- Alembic
- PostgreSQL
- Valkey
- Pydantic v2
- Dependency Injector
- Ruff
- Pytest

## Architecture

The backend follows a hexagonal structure:

```text
app/<domain>/
  domain/
    command/
    entity/
    repository/
    usecase/
  application/
    exception/
    service/
    dto/        # only when a dedicated result model is needed
  adapter/
    input/api/v1/
      request/
      response/
      <domain>.py
    output/persistence/
      sqlalchemy/
      valkey/
  container.py
```

Key rules:

- `application/service` depends on domain ports, not adapter wrappers
- `adapter/input` owns HTTP request/response models
- `domain/command` owns use-case input models
- `domain/usecase` owns use-case interfaces
- `adapter/output` implements persistence ports

Planned Dialearn domains include assessment, classroom, learning material, conversational evaluation, and reporting.

More detail:

- `docs/architecture.md`
- `docs/authentication.md`
- `docs/creating-a-domain.md`

## Quick Start

1. Install dependencies

```bash
uv sync --all-groups
```

2. Copy environment file

```bash
cp .env.example .env
```

3. Start local dependencies

```bash
docker compose up -d
```

4. Apply migrations for the local test database

```bash
ENVIRONMENT=test DATABASE_URL=postgresql+asyncpg://postgres:password@127.0.0.1:55432/test_db VALKEY_URL=redis://127.0.0.1:6379/0 uv run alembic upgrade head
```

5. Run tests

```bash
ENVIRONMENT=test DATABASE_URL=postgresql+asyncpg://postgres:password@127.0.0.1:55432/test_db VALKEY_URL=redis://127.0.0.1:6379/0 uv run pytest
```

6. Run the development server

```bash
uv run uvicorn main:app --reload
```

## Local Services

`docker-compose.yml` provides:

- PostgreSQL on `127.0.0.1:55432`
- Valkey on `127.0.0.1:6379`

Useful commands:

```bash
docker compose up -d
docker compose ps
docker compose down -v
```

## Auth Overview

- Access token and refresh token are issued as `HttpOnly` cookies
- Refresh tokens are stored in Valkey
- Refresh token storage key format:

```text
auth:user:{user_id}:refresh:{jti}
```

- Built-in endpoints:
  - `POST /api/auth/login`
  - `POST /api/auth/refresh`
  - `POST /api/auth/logout`

See `docs/authentication.md` for the full flow.

## Quality Gate

Run the same checks as CI:

```bash
uv run ruff check .
uv run ruff format --check .
ENVIRONMENT=test DATABASE_URL=postgresql+asyncpg://postgres:password@127.0.0.1:55432/test_db VALKEY_URL=redis://127.0.0.1:6379/0 uv run pytest
```

## Creating a New Domain

Use the same structure as `user`, `auth`, and `file`.

Start with:

- `domain/command`
- `domain/entity`
- `domain/repository`
- `domain/usecase`
- `application/service`
- `application/exception`
- `adapter/input/api/v1/request`
- `adapter/input/api/v1/response`
- `adapter/output/persistence/sqlalchemy`
- `container.py`
- tests for domain, service, and API

Detailed guidance lives in `docs/creating-a-domain.md`.
