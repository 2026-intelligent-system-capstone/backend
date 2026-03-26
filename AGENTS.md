# AGENTS.md
This file is for coding agents working in `backend/`.

## Repository Snapshot
- Python backend managed with `uv`
- FastAPI boilerplate with dependency-injector, SQLAlchemy async ORM, Alembic, PostgreSQL, and Valkey
- Main entrypoint is `main.py`; `create_app()` builds the app and `app` is the ASGI export
- Main code lives in `app/` and `core/`; tests live in `tests/`; migrations live in `alembic/`
- Built-in modules include `user`, `auth`, and `file`; treat them as default boilerplate modules, not throwaway samples
- The project is intended to be reused as a starter template, so prefer generic naming and reusable defaults over product-specific wording

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
  - Container names are `fastapi-hexagonal-boilerplate-postgres` and `fastapi-hexagonal-boilerplate-valkey`
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
- Treat `core/` as technical infrastructure only; do not place classroom, organization, user, auth, enrollment, or other product rules there
- If logic mentions a domain noun such as classroom, organization, student, professor, membership, invitation, or organization-scoped visibility, it belongs in `app/<domain>/...`, not in `core/`
- Put reusable technical primitives in `core/`; put reusable business rules in the owning domain, even if multiple endpoints reuse them
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

## Common Vs Domain Logic
- Common logic means framework wiring, middleware, base request/response types, shared exception plumbing, DB/session helpers, and other cross-domain technical utilities
- Domain logic means rules tied to business data or vocabulary, such as classroom membership, invited-student visibility, professor/admin authority, organization scoping, and user lifecycle policy
- If renaming `classroom` or `organization` to another domain would change the rule, that rule is domain logic and must not go into `core/`
- If code needs `CurrentUser`, `organization_id`, a domain entity, or repository data to decide behavior, prefer `app/<domain>/application` or the owning auth/domain module, not shared infrastructure
- Keep `core/` generic enough to be reused by multiple domains without knowing business meaning; once a helper encodes product policy, move it out of `core/`

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
- Keep shared FastAPI authentication and authorization infrastructure under `core/fastapi/`, not inside a business domain package
- Route authorization is class-based in `core/fastapi/dependencies/permission.py`
- Permission classes should inherit from `BasePermission` and implement async `has_permission(request)`
- Pass permission classes into `PermissionDependency([...])`; do not inline ad hoc role checks in routers
- Use `dependencies=[Depends(PermissionDependency([...]))]` when a route only needs access gating
- Use `current_user: CurrentUser = Depends(get_current_user)` when the use case needs actor context after permission gating
- Keep route-level dependencies generic, such as `IsAuthenticated`, `IsAdmin`, or `IsProfessorOrAdmin`; resource-specific authorization must live in the owning use case/service
- Do not duplicate resource ownership or membership checks in routers; re-check them inside the application service after loading the target resource
- Keep HTTP request/response Pydantic models in the API adapter layer, for example `request/__init__.py` and `response/__init__.py`
- Keep command models in `domain/command/` and pass them from routers to use cases/services
- Type router dependencies with domain use case interfaces when possible
- Keep path params strongly typed, for example `user_id: UUID`
- In typical CRUD flows, convert `Request -> Command` in the router and pass commands to the service
- In typical CRUD flows, build response payloads directly in the router when mapping is simple and local
- Do not add simple router helper functions like `_to_payload`, `_build_auth_response`, or similar wrappers when inline mapping is short and local
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
  - shared authentication/authorization dependency in `core/fastapi/dependencies/permission.py`
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
- Compose authorization at the API adapter boundary before calling services/use cases
- When actor context is needed, pass `CurrentUser` from the router into the use case via `Depends(get_current_user)`; do not re-decode tokens or repeat role checks in routers
- If a rule depends on both actor and target resource, enforce it in the application service after loading the resource, not in the router
- If the user intentionally changes an API contract, keep the implementation aligned with that contract and update tests instead of restoring older behavior
- Auth routes may intentionally `return None` when cookies are the meaningful output; do not restore response bodies unless explicitly requested
- Do not make application services depend on adapter wrapper classes; depend on domain repository ports directly
- Add `result.py` only if multiple adapters share the same read model or the service should stop returning entities

## Domain And Service Conventions
- Domain entities are dataclass-based and should remain framework-light
- Value objects belong in domain or shared model layers, not routers
- The current `User` entity is flat and should stay that way: use direct fields such as `organization_id`, `login_id`, `role`, `email`, `name`, `status`, and `is_deleted`; do not reintroduce nested profile-style value objects for user metadata
- Application services are async and own business logic
- Application services own domain authorization beyond basic authentication, such as resource visibility, membership, management authority, and organization-scoped access rules
- Keep aggregate-specific validation with the aggregate's service; for example, classroom membership and classroom manager checks stay in `app/classroom`, even if they read `UserRepository`
- Domain/application code may depend on other domain repositories to validate business relationships, but should not move those relationship rules into `core/` just because they are reused
- Apply `@transactional` to write operations that should commit or roll back atomically
- Keep read operations simple and avoid transactions unless existing patterns require them

## Error Handling
- Raise app-specific exceptions for expected business failures
- Reuse `CustomException` subclasses so APIs return consistent `error_code`, `message`, and `detail`
- Use `404`-style exceptions for missing resources and `400`-style exceptions for business conflicts
- `IsAuthenticated` failures should raise `AuthUnauthorizedException`; role or permission failures should raise `AuthForbiddenException`
- Prefer adding reusable permission classes in `core/fastapi/dependencies/permission.py` for shared route-level authorization, and keep resource-specific access failures in application/domain code
- Use auth exceptions for authentication or coarse authorization failures only; use domain exceptions for state conflicts, invalid membership, and missing domain-linked actors
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

## User-Specific Working Rules
- Treat ManyFast as the product source of truth when implementing product behavior; re-read it before building domain features that depend on requirements or user flows
- Use Context7 when the user explicitly requests library/documentation-backed implementation guidance
- Keep input adapters thin: dependency wiring, request validation/translation, and direct response mapping only
- Do not put business or resource-specific rules in `adapter/input`; keep them in use cases and application services
- Avoid reintroducing patterns the user intentionally removed, even if older tests expected them; update tests to match the intended behavior
- Prefer direct inline response mapping in routers over tiny helper wrappers when the mapping is short and local
- Follow the established workflow rule: when a task is complete, create a Conventional Commit and push when appropriate for the branch workflow
