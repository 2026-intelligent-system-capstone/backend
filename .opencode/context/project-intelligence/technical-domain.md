<!-- Context: project-intelligence/technical | Priority: critical | Version: 1.4 | Updated: 2026-03-25 -->

# Technical Domain

**Purpose**: 이 프로젝트의 기술 스택, 아키텍처, 구현 패턴을 빠르게 파악하기 위한 기준 문서.
**Last Updated**: 2026-03-25

## Quick Reference
- **Architecture**: FastAPI + Hexagonal Architecture + dependency-injector
- **Persistence**: SQLAlchemy async ORM + Alembic + PostgreSQL + Valkey
- **Quality Gate**: Ruff lint/format + Pytest + bootstrap smoke test
- **API Style**: Request -> Command -> UseCase(Service) -> Response mapping

## Primary Stack
| Layer | Technology | Notes |
|------|-----------|-------|
| Language | Python 3.13+ | Ruff target `py314`, CI uses Python `3.14.3` |
| Framework | FastAPI | `create_app()` 기반 앱 조립 |
| Architecture | Hexagonal Architecture | `app/<domain>` + `core/` 분리 |
| Database | PostgreSQL | `asyncpg` 기반 async 연결 |
| In-Memory | Valkey | refresh token 저장소 |
| ORM/Migration | SQLAlchemy + Alembic | async session + migration 관리 |
| DI | dependency-injector | 컨테이너별 서비스 주입 |
| Quality | Ruff + Pytest | lint, format, test 표준화 |
| CI/CD | GitHub Actions | lint -> migration -> startup -> test |

## Architecture Notes
- 앱 진입점은 `main.py`의 `create_app()`이며 컨테이너, 미들웨어, 라우터를 조립한다.
- 도메인별 구조는 `domain`, `application`, `adapter`로 나누고 공통 인프라는 `core/`에 둔다.
- 라우터는 `core/fastapi/router.py`에서 `/api` prefix로 통합 등록한다.
- 영속성은 SQLAlchemy repository adapter와 Valkey adapter로 나뉜다.

## Key Patterns
**API Endpoint**
- `APIRouter(prefix=..., tags=[...])` 사용
- 요청 모델은 `adapter/input/api/v1/request`
- 라우터에서 `Request -> Command` 변환
- `Depends(Provide[...])`로 UseCase 주입
- 응답은 `...Payload`, `...Response`, `...ListResponse`로 감싼다
- 에러 응답 형식은 공통 예외 구조로 일관되게 유지한다
- 인증은 쿠키 기반 흐름만 사용한다
- 라우터 helper 함수 추가를 최소화한다
- 라우터에는 비즈니스/도메인 로직을 두지 않는다

```python
@router.post("", response_model=UserResponse)
@inject
async def create_user(
    request: CreateUserRequest,
    usecase: UserUseCase = Depends(Provide[UserContainer.service]),
):
    user = await usecase.create_user(CreateUserCommand(**request.model_dump()))
    return UserResponse(data=UserPayload(...))
```

**Service / UseCase**
- 서비스는 `application/service`에 위치
- 서비스는 `domain.usecase` 인터페이스 구현
- 비즈니스 규칙은 서비스가 담당
- 저장은 repository port를 통해 수행
- 쓰기 작업은 `@transactional` 적용
- 도메인을 빈 껍데기로 두지 않고 풍부하게 설계한다
- 도메인 계층에서 표현 가능한 규칙은 도메인 계층에 우선 배치한다

```python
class UserService(UserUseCase):
    def __init__(self, *, repository: UserRepository):
        self.repository = repository

    @transactional
    async def create_user(self, command: CreateUserCommand) -> User:
        ...
```

## Naming Conventions
| Type | Convention | Example |
|------|-----------|---------|
| Modules | snake_case | `user.py`, `permission.py` |
| Classes | PascalCase | `UserService`, `CreateUserRequest` |
| Functions | snake_case | `create_user`, `get_current_user` |
| Request Models | `...Request` | `CreateUserRequest` |
| Command Models | `...Command` | `UpdateUserCommand` |
| Response Payload | `...Payload` | `UserPayload` |
| Response Envelope | `...Response` / `...ListResponse` | `UserResponse` |
| UseCase | `...UseCase` | `UserUseCase` |
| Repository | noun-based | `UserRepository` |

## Code Standards
- FastAPI input adapter는 얇게 유지하고 비즈니스 규칙은 service/usecase에 둔다.
- domain/application은 repository abstraction에 의존하고 구현체 결합을 피한다.
- 요청 검증은 Pydantic `BaseRequest(extra="forbid")` 기반으로 처리한다.
- 쓰기 작업은 `@transactional`로 감싸고 rollback/commit을 일관되게 유지한다.
- 응답 매핑은 라우터에서 직접 수행하고 작은 helper 남발을 피한다.
- 테스트 가능한 구조를 우선하고 결합도를 낮춘다.
- 서비스 구현은 유스케이스 단위로 작게 유지한다.
- 공통 로직처럼 보여도 도메인 의미가 있으면 `core/`가 아니라 해당 도메인에 둔다.
- Pydantic은 요청/응답 경계에서만 사용하고 내부 규칙은 도메인 모델로 표현한다.

## Security Requirements
- 인증은 access token 쿠키 기반이며 JWT 타입 검증을 수행한다.
- access/refresh token은 분리하고 refresh token은 Valkey에 저장한다.
- 인증 쿠키는 `httponly` 옵션으로 설정한다.
- 권한 검사는 `PermissionDependency` + `BasePermission` 계층으로 수행한다.
- 입력은 strict Pydantic schema와 `extra="forbid"`로 제한한다.
- refresh token은 In-Memory Database 계층인 Valkey에 저장한다.
- 조직/리소스 소유권 검사는 서비스에서 반드시 재확인한다.
- 민감 정보는 응답에 직접 노출하지 않는다.
- soft delete 데이터는 기본 조회에서 제외한다.
- 인증/인가 실패 시 과도한 내부 정보를 노출하지 않는다.

## Testing & Operations
- CI는 GitHub Actions에서 lint 후 test 순서로 실행된다.
- 테스트 전 Alembic migration과 앱 bootstrap smoke test를 수행한다.
- API 테스트는 `TestClient(create_app())`와 monkeypatch 패턴을 자주 사용한다.
- 기능 작업은 TDD를 기본으로 하며 구현 전에 실패하는 테스트를 먼저 작성한다.
- 기본 순서는 `실패하는 테스트 작성 -> 최소 구현 -> 테스트 통과 -> 리팩터링`이다.
- 가능하면 기존 테스트는 수정하지 않고 새 테스트 추가로 검증 범위를 넓힌다.
- 기존 테스트 수정은 계약 변경, 잘못된 테스트, 깨진 테스트 인프라처럼 불가피한 경우로 제한한다.
- Alembic 실행 시 `-x env=local|dev|test|prod`로 환경을 명시할 수 있다.
- DB migration 전에는 `current -> upgrade --sql -> -x dry-run upgrade -> 실제 upgrade` 순서를 항상 따른다.
- 스키마 변경 시에는 `alembic revision --autogenerate`를 우선 사용하고 migration 파일 수동 수정은 최소화한다.

## 📂 Codebase References
- `pyproject.toml` - Python, Ruff, Pytest, 주요 의존성 정의
- `.github/workflows/ci.yml` - CI 파이프라인과 검증 순서
- `main.py` - 앱 생성과 초기 조립
- `app/container.py` - 모듈별 DI 컨테이너 조립
- `app/user/adapter/input/api/v1/user.py` - 대표 CRUD API 패턴
- `app/auth/adapter/input/api/v1/auth.py` - 쿠키 기반 인증 패턴
- `app/user/application/service/user.py` - 서비스 계층 규칙
- `core/common/request/base.py` - 요청 검증 및 strict schema 정책
- `core/fastapi/dependencies/permission.py` - 인증/권한 구조
- `core/helpers/token.py` - JWT 발급/검증
- `core/db/session.py` - async SQLAlchemy session 구성
- `alembic/env.py` - env 기반 Alembic 실행과 dry-run 지원
- `alembic/versions/a2d651fa6123_add_classroom_domain.py` - classroom 테이블 생성 migration
- `alembic/versions/daf876d85767_add_classroom_materials.py` - classroom material 테이블 생성 migration

## Related Files
- `business-domain.md` - 비즈니스 배경과 문제 정의
- `business-tech-bridge.md` - 비즈니스 요구와 기술 설계 연결
- `decisions-log.md` - 주요 기술 의사결정 기록
