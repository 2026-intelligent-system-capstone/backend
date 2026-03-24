# AGENTS.md
This file is for coding agents working in `backend/`.

## Repository Snapshot
- Python backend managed with `uv`
- FastAPI boilerplate with dependency-injector, SQLAlchemy async ORM, Alembic, PostgreSQL, and Valkey
- Main entrypoint is `main.py`; `create_app()` builds the app and `app` is the ASGI export
- Main code lives in `app/` and `core/`; tests live in `tests/`; migrations live in `alembic/`
- Built-in modules include `user`, `auth`, and `file`; treat them as default boilerplate modules, not throwaway samples

## Source Of Truth
- Read `pyproject.toml` for Python, Ruff, and pytest settings
- Read `.github/workflows/ci.yml` for the exact CI commands and required services
- No Cursor rules were found in `.cursor/rules/` or `.cursorrules`
- No Copilot instructions were found in `.github/copilot-instructions.md`
- If those files appear later, merge their repo-specific rules into this file rather than conflicting with them

## Setup And Runtime
- Install deps: `uv sync`
- Install dev deps too: `uv sync --all-groups`
- Python requirement in project metadata: `>=3.13`
- CI installs Python `3.14.3`; prefer matching CI when possible
- Copy env if needed: `.env.example` -> `.env`
- Run dev server: `uv run uvicorn main:app --reload`
- Quick startup check: `uv run python -c "from main import create_app; create_app()"`

## Build, Lint, And Format
- There is no separate build step; treat lint + tests + startup as the quality gate
- Lint exactly as CI: `uv run ruff check .`
- Format check exactly as CI: `uv run ruff format --check .`
- Auto-fix lint when safe: `uv run ruff check . --fix`
- Format files: `uv run ruff format .`
- Lint one file: `uv run ruff check path/to/file.py`
- Format one file: `uv run ruff format path/to/file.py`

## Test Commands
- Run all tests: `uv run pytest`
- Quiet output: `uv run pytest -q`
- Stop on first failure: `uv run pytest -x`
- Run one file: `uv run pytest tests/app/user/application/test_user_service.py`
- Run one test: `uv run pytest tests/app/user/application/test_user_service.py::test_create_user_success`
- Run one parametrized case or nested node: `uv run pytest path/to/test_file.py::test_name[case-id]`
- Run by keyword: `uv run pytest -k create_user`

## Test Environment
- `pytest` config is in `pyproject.toml`
- Async tests use `asyncio_mode = auto`
- CI starts PostgreSQL and Valkey before `uv run pytest`
- Useful env for integration-style tests:
  - `DATABASE_URL=postgresql+asyncpg://postgres:password@127.0.0.1:55432/test_db`
  - `VALKEY_URL=redis://localhost:6379/0`
  - `ENVIRONMENT=test`
- Repository tests and some startup flows likely need those services
- Many service and API tests can stay isolated with in-memory fakes or monkeypatching
- Local Docker Compose is available for test dependencies:
  - Start services: `docker compose up -d`
  - Check health: `docker compose ps`
  - Stop and remove volumes: `docker compose down -v`
  - PostgreSQL is exposed on `127.0.0.1:55432`
  - Valkey is exposed on `127.0.0.1:6379`
- Before DB-backed test runs, apply migrations with the test env vars set:
  - `ENVIRONMENT=test DATABASE_URL=postgresql+asyncpg://postgres:password@127.0.0.1:55432/test_db VALKEY_URL=redis://127.0.0.1:6379/0 uv run alembic upgrade head`

## Alembic And Data Layer Commands
- Upgrade DB: `uv run alembic upgrade head`
- Create migration: `uv run alembic revision --autogenerate -m "describe change"`
- Downgrade one revision: `uv run alembic downgrade -1`

## CI Notes
- CI workflow file: `.github/workflows/ci.yml`
- CI order is `lint` then `test`
- Lint job runs `uv sync`, `uv run ruff check .`, and `uv run ruff format --check .`
- Test job runs `uv run pytest` with test DB and Valkey env vars
- Keep local validation aligned with CI unless you have a strong reason not to

## Architecture Conventions
- Preserve the layered structure already in use:
  - `app/<domain>/domain/` for commands, entities, repository interfaces, and use case interfaces
  - `app/<domain>/application/` for services, DTOs, and app exceptions
  - `app/<domain>/adapter/` for API and persistence adapters
  - `core/` for shared config, DB, framework, and helpers
- Keep routers thin and business rules in application services
- Depend on repository abstractions from services, not directly on SQLAlchemy internals
- Keep persistence adapters in adapter/output modules, not in services or routers
- Prefer this boundary for new API work:
  - `adapter/input/api/v1/request/__init__.py` for HTTP request models
  - `domain/command/__init__.py` for use-case command models
  - `domain/usecase/*.py` for use-case interfaces
  - `adapter/input/api/v1/response/__init__.py` for HTTP response models
  - `adapter/output/persistence/sqlalchemy/*.py` for concrete SQLAlchemy repositories
  - `adapter/output/persistence/valkey/*.py` for concrete Valkey repositories when in-memory storage is needed
  - `application/dto/result.py` only when a non-HTTP use-case output model is actually needed

## Imports
- Follow Ruff/isort ordering: standard library, third-party, then local imports
- Respect the 80-character limit; use parenthesized multiline imports when needed
- Avoid wildcard imports
- Prefer direct imports from defining modules over long re-export chains

## Formatting
- Use Ruff formatting defaults from `pyproject.toml`
- Line length is `80`
- Indentation is 4 spaces
- Quote style is double quotes
- Let Ruff control wrapping rather than manually aligning code
- Avoid trailing whitespace and formatting-only churn outside the requested scope

## Typing
- Add explicit type hints on public functions, methods, and important locals
- Use modern typing syntax like `str | None`, `list[User]`, and `dict[str, User]`
- Match the existing modern style, including `type Alias = ...` where useful
- Keep async repository and service return types precise
- Prefer strong domain types such as `UUID` internally instead of plain strings
- Use Pydantic models at request/response boundaries rather than raw dicts

## Naming
- Modules are lowercase and domain-oriented
- Classes use PascalCase
- Functions, methods, and variables use snake_case
- Tests use `test_*.py` files and `test_<behavior>` functions
- API request models use `...Request`, for example `CreateUserRequest`
- Domain command models use `...Command`, for example `UpdateUserCommand`
- API response payload models use `...Payload`, for example `UserPayload`
- API response envelope models use `...Response` and `...ListResponse`, for example `UserResponse` and `UserListResponse`
- Use case interfaces use `...UseCase`, for example `UserUseCase`
- Exception classes end with `Exception`
- Repository interfaces are noun-based, such as `UserRepository`

## FastAPI Patterns
- Define routes under adapter input modules such as `app/.../adapter/input/api/v1/`
- Use `APIRouter` with explicit `prefix` and `tags`
- Wire dependencies with `Depends(Provide[...])`
- Keep HTTP request/response Pydantic models in the API adapter layer, for example `request/__init__.py` and `response/__init__.py`
- Keep command models in `domain/command/` and pass them from routers to use cases/services
- Type router dependencies with domain use case interfaces when possible
- Keep path params strongly typed, for example `user_id: UUID`
- In typical CRUD flows, convert `Request -> Command` in the router and pass commands to the service
- In typical CRUD flows, build response payloads directly in the router when mapping is simple and local
- Prefer one single-item response envelope plus one list response envelope per resource over per-method wrappers
- Avoid classes like `CreateUserResponse` or `DeleteUserResponse` unless the response shapes actually differ
- Return typed wrapper DTOs instead of loose response dicts when wrappers already exist

## Pydantic Conventions
- Shared request models inherit from `BaseRequest`
- `BaseRequest` sets `extra="forbid"`; keep new request schemas strict by default
- Use `Field(...)` for constraints, patterns, and metadata
- Use validators for cross-field rules and non-empty update payloads
- Keep normalization and empty-string/null handling inside schema classes when possible
- Prefer explicit response fields over leaking domain entities directly through FastAPI

## Current API Pattern
- The current preferred pattern is:
  - request schema in `adapter/input/api/v1/request/__init__.py`
  - command model in `domain/command/__init__.py`
  - use case interface in `domain/usecase/*.py`
  - response payload and envelopes in `adapter/input/api/v1/response/__init__.py`
  - service implementation in `application/service/*.py`
  - repository port in `domain/repository/*.py`
  - concrete persistence in `adapter/output/persistence/sqlalchemy/*.py` or `adapter/output/persistence/valkey/*.py`
  - service returns domain entities unless a dedicated result model is justified
- A representative naming set is:
  - `CreateUserRequest`, `UpdateUserRequest`
  - `CreateUserCommand`, `UpdateUserCommand`
  - `UserUseCase`
  - `UserPayload`
  - `UserResponse`, `UserListResponse`
- Do not place command models in `application/dto/command.py`
- Do not place HTTP response models in `application/dto/response.py`
- Do not place FastAPI request models outside the adapter input layer
- Do not make application services depend on adapter wrapper classes; depend on domain repository ports directly
- Add `result.py` only if multiple adapters share the same read model or the service should stop returning entities

## Domain And Service Conventions
- Domain entities are dataclass-based and should remain framework-light
- Value objects belong in domain or shared model layers, not routers
- Application services are async and own business logic
- Apply `@transactional` to write operations that should commit or roll back atomically
- Keep read operations simple and avoid transactions unless existing patterns require them

## Error Handling
- Raise app-specific exceptions for expected business failures
- Reuse `CustomException` subclasses so APIs return consistent `error_code`, `message`, and `detail`
- Use `404`-style exceptions for missing resources and `400`-style exceptions for business conflicts
- Let FastAPI/Pydantic validation errors flow into the existing `SERVER__REQUEST_VALIDATION_ERROR` handler
- Do not swallow exceptions silently
- Roll back DB work on failures inside transactional flows

## Database And Persistence
- Keep DB access async end-to-end
- Reuse the shared session machinery in `core/db/session.py`
- Keep ORM table definitions under `core/db/sqlalchemy/models/`
- Keep ORM mappings and domain mapping concerns in the existing SQLAlchemy mapping modules
- When schema changes, update models and add an Alembic migration together
- Preserve optimistic locking/version fields unless a task explicitly changes concurrency behavior

## Testing Style
- Prefer focused unit tests first, especially for service logic
- For API tests, `TestClient(create_app())` plus monkeypatching is preferred when full integration is unnecessary
- For repository tests, isolate DB setup and cleanup carefully
- Assert both status codes and structured error payloads for failure cases
- Keep fixtures small and local unless there is clear reuse value
- Cover success paths and relevant failure/conflict cases for new behavior

## Editing Guidance
- Match existing patterns before introducing new abstractions
- Keep diffs minimal and architecture-consistent
- Do not broaden scope with unrelated cleanup unless requested
- If you touch a file, keep imports Ruff-compliant and formatting clean
- If you add commands or workflows, make sure they work with `uv`
