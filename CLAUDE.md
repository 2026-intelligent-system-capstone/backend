# Backend CLAUDE.md

## 역할과 범위

`backend/`는 Dialearn의 프로덕션 FastAPI 백엔드다. Bloom's Taxonomy 기반 구술 시험 생성, 진행, 평가를 위한 HTTP API, 인증, 영속성, 비동기 작업, 파일/자료 처리를 담당한다.

이 디렉터리는 독립 Git 리포지토리다. Git 명령은 워크스페이스 루트가 아니라 반드시 `backend/` 안에서 실행한다.

## 스택

- Python 3.13+
- FastAPI, Pydantic v2, pydantic-settings
- SQLAlchemy async ORM, Alembic, asyncpg, PostgreSQL
- Valkey 기반 refresh token / async job 저장소
- dependency-injector 기반 컨테이너 wiring
- OpenAI, Qdrant, boto3/R2, pypdf 연동
- Ruff, pytest, pytest-asyncio, pytest-mock

`main.py`의 `create_app()`이 앱을 생성하고, `app = create_app()`이 ASGI export다. 앱 부트스트랩은 ORM mapper 초기화, `AppContainer` 생성, middleware/lifespan/router/OpenAPI security/exception handler 등록 순서로 이뤄진다.

## 명령어

모든 Python 명령은 `cd /Users/user/Desktop/dev/univ/grade_4/intelligent-system-capstone/backend && ...` 형식으로 실행한다. 테스트 실행은 별도 확인 없이 바로 진행한다.

<!-- SOURCE-DERIVED: backend commands from pyproject, alembic, docker-compose -->
| 명령 | 용도 |
|---|---|
| `uv sync --all-groups` | 런타임 및 dev 의존성 설치 |
| `cp .env.example .env` | 로컬 환경 파일 생성 |
| `docker compose up -d` | compose stack 실행; backend 서비스에는 `.env.app` 준비가 필요 |
| `uv run uvicorn main:app --reload` | 개발 서버 실행 |
| `uv run python -c "from main import create_app; create_app()"` | 앱 부트스트랩 스모크 테스트 |
| `uv run ruff check .` | Ruff lint 검사 |
| `uv run ruff check . --fix` | 자동 수정 가능한 lint 이슈 수정 |
| `uv run ruff format --check .` | 포맷 검증 |
| `uv run ruff format .` | 포맷 적용 |
| `uv run pytest` | 전체 테스트 실행 |
| `uv run pytest -q` | 간결한 테스트 실행 |
| `uv run pytest -x` | 첫 실패에서 중단 |
| `uv run alembic upgrade head` | 최신 migration 적용 |
| `uv run alembic revision --autogenerate -m "message"` | 모델 변경 기반 migration 생성 |
| `uv run alembic downgrade -1` | migration 한 단계 되돌림 |
<!-- /SOURCE-DERIVED -->

DB 기반 테스트 전에는 `.env.test`의 `DATABASE_URL`이 가리키는 `test_db`와 Valkey 인스턴스가 실제로 준비되어 있어야 한다. 현재 compose 파일은 운영형 full stack에 가깝고 backend 서비스는 `.env.app`을 요구하므로, 로컬 테스트용 DB/Valkey만 쓰려면 호스트 포트 공개나 별도 override를 확인한 뒤 migration을 적용한다.

```bash
cd /Users/user/Desktop/dev/univ/grade_4/intelligent-system-capstone/backend && ENVIRONMENT=test DATABASE_URL=postgresql+asyncpg://postgres:password@127.0.0.1:55432/test_db VALKEY_URL=redis://127.0.0.1:6379/0 uv run alembic upgrade head
cd /Users/user/Desktop/dev/univ/grade_4/intelligent-system-capstone/backend && ENVIRONMENT=test DATABASE_URL=postgresql+asyncpg://postgres:password@127.0.0.1:55432/test_db VALKEY_URL=redis://127.0.0.1:6379/0 uv run pytest
```

## 환경 변수

<!-- SOURCE-DERIVED: backend env from .env.example -->
| 영역 | 주요 변수 |
|---|---|
| App | `ENV`, `APP_NAME`, `APP_DESCRIPTION`, `APP_VERSION`, `API_PREFIX`, `DOCS_URL`, `REDOC_URL`, `OPENAPI_URL` |
| JWT | `ALGORITHM`, `ACCESS_TOKEN_SECRET_KEY`, `REFRESH_TOKEN_SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_MINUTES`, `ACCESS_TOKEN_COOKIE_NAME`, `REFRESH_TOKEN_COOKIE_NAME`, `AUTH_COOKIE_SECURE`, `AUTH_COOKIE_SAMESITE` |
| Storage | `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_REGION_NAME` |
| Runtime | `DEBUG`, `SQLALCHEMY_ECHO`, `FRONTEND_CORS_ORIGIN`, `LOG_LEVEL`, `LOG_FORMAT`, `LOG_DEBUG` |
| Database | `DATABASE_URL`, `VALKEY_URL` |
<!-- /SOURCE-DERIVED -->

운영 환경에서는 기본 JWT secret을 절대 사용하지 말고, `AUTH_COOKIE_SECURE=true`, 신뢰 가능한 CORS origin, 관리형 PostgreSQL/Valkey를 설정한다.

## 아키텍처

백엔드는 도메인별 Hexagonal Architecture를 따른다. 핵심 목표는 비즈니스 규칙을 FastAPI, SQLAlchemy, Valkey, 외부 API 같은 기술 세부사항에서 분리하는 것이다.

```text
app/<domain>/
  domain/          # command, entity, repository port, domain service, use-case interface
  application/     # service, DTO/result, application exception
  adapter/input/   # FastAPI router, request schema, response schema
  adapter/output/  # SQLAlchemy, Valkey, R2, 외부 시스템 adapter
  container.py
```

허용 의존 방향은 `adapter -> application -> domain`, `adapter -> domain`, `application -> domain`이다. `domain`은 application/adapter/framework에 의존하지 않고, `application`은 input adapter나 concrete persistence adapter에 의존하지 않는다.

현재 주요 도메인은 `async_job`, `auth`, `classroom`, `exam`, `file`, `organization`, `user`다.

## 레이어 배치 규칙

- `domain/command`: use-case 입력 모델.
- `domain/entity`: 엔티티와 값 객체. 도메인 invariant는 가능하면 여기서 표현한다.
- `domain/repository`: repository port. application service는 이 port에 의존한다.
- `domain/service`: 여러 엔티티를 조합하는 순수 도메인 규칙.
- `domain/usecase`: use-case interface.
- `application/service`: use-case 구현, transaction boundary, 리소스 로드 후 authorization.
- `application/exception`: 비즈니스 실패를 표현하는 application exception.
- `adapter/input/api/v1`: request/response schema와 router.
- `adapter/output`: repository port를 구현하는 SQLAlchemy/Valkey/R2/external adapter.
- `core/`: config, DB/session, FastAPI glue, middleware, OpenAPI, 공통 infrastructure 전용.

classroom, organization, exam, professor/student role, membership, visibility, management authority 같은 제품 규칙은 `core/` helper가 아니라 소유 도메인의 entity/domain service/application service에 둔다. service helper를 늘리기보다 엔티티와 도메인 모델을 풍부하게 만드는 방향을 우선한다.

## Router, Service, Repository 경계

Router는 얇게 유지한다.

- dependency wiring
- request validation 및 `Request -> Command` 변환
- use case 호출
- 단순 response mapping

Application service는 다음을 담당한다.

- 대상 리소스 로드
- actor와 target resource를 함께 보는 authorization
- membership, visibility, management authority, organization-scoped access 규칙
- write operation의 transaction boundary

Router에서 resource ownership, membership, visibility 같은 규칙을 중복 검사하지 않는다. route-level dependency는 인증과 coarse authorization에 제한한다.

## 새 도메인 추가 순서

1. domain entity/value object 작성
2. command 모델 작성
3. repository port 정의
4. use-case interface 정의
5. application service 구현
6. request/response schema 작성
7. router 추가
8. output persistence adapter 구현
9. `container.py` wiring
10. domain/application/API/persistence 테스트 추가

명명은 `CreateThingRequest`, `CreateThingCommand`, `ThingPayload`, `ThingResponse`, `ThingUseCase`, `ThingRepository`처럼 역할이 드러나게 한다.

## 인증

인증은 JWT cookie 기반 세션 흐름이다.

- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`

Access token은 짧게, refresh token은 길게 유지하며 둘 다 `HttpOnly` cookie로 전달한다. Refresh token은 Valkey에 저장하고 key 형식은 `auth:user:{user_id}:refresh:{jti}`다. Refresh 시 기존 token을 삭제하고 새 token을 저장한다.

## 데이터베이스와 migration

ORM 테이블 정의는 `core/db/sqlalchemy/models/` 아래에 둔다. 스키마 변경은 SQLAlchemy 모델 변경과 Alembic migration을 한 작업으로 묶고, autogenerate 결과를 반드시 검토한다.

Compose 기준 health check는 `GET /api/healthz`다. `.env.example`과 `.env.test`는 PostgreSQL `127.0.0.1:55432`, Valkey `127.0.0.1:6379`를 기준으로 하지만, 현재 `docker-compose.yml` 자체는 해당 포트를 publish하지 않으므로 로컬 테스트 시 compose override나 별도 로컬 서비스를 확인한다.

## 코딩 스타일

- Python public function에는 타입 힌트를 둔다.
- Ruff 설정은 line length 80, double quote, space indent를 기준으로 한다.
- `print()` 대신 logging을 사용한다.
- user input, API 응답, 파일 내용, 환경 변수 같은 경계 입력은 명시적으로 검증한다.
- 예외를 조용히 삼키지 말고 application/domain 의미가 있는 오류로 변환한다.
- 하드코딩 secret, token, password를 금지한다.
- Python/backend 확인·수정은 WebStorm보다 PyCharm MCP를 우선 사용한다.

## 테스트 지침

- 새 동작은 테스트를 먼저 작성한다.
- domain/entity와 application/service 단위 테스트를 우선한다.
- API 테스트는 full integration이 필요하지 않으면 `TestClient(create_app())`와 monkeypatching으로 격리한다.
- Repository 테스트는 DB setup/cleanup을 명확히 분리한다.
- 성공 경로뿐 아니라 conflict, authorization, validation 실패 경로를 포함한다.
- 실패 케이스는 status code와 structured error payload를 함께 검증한다.

## 참고 문서

- `docs/architecture.md`: 레이어 책임과 의존 방향
- `docs/creating-a-domain.md`: 새 도메인 추가 절차
- `docs/authentication.md`: JWT cookie/Valkey 인증 흐름
