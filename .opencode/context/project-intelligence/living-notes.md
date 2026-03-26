<!-- Context: project-intelligence/notes | Priority: high | Version: 1.2 | Updated: 2026-03-25 -->

# Living Notes

**Purpose**: 현재 운영 이슈, 기술 부채, 유지보수자가 바로 알아야 할 주의사항을 남기는 작업 메모.
**Last Updated**: 2026-03-25

## Quick Reference
- **Current Focus**: 헥사고날 경계 정리 + DB migration 운영 안정화
- **Recent Incident**: `t_classroom` 누락으로 `/api/classrooms` 500 발생 후 해결
- **Migration Rule**: `current -> --sql -> dry-run -> upgrade`
- **Env Rule**: Alembic은 항상 `-x env=...`와 함께 실행
- **Testing Rule**: 구현 전 테스트 작성, 기존 테스트 수정 최소화

## Active Notes
**Resolved Incident: classroom schema drift**
- **Impact**: dev 환경에서 `/api/classrooms` 조회 시 500 발생
- **Root Cause**: DB revision이 head보다 뒤처져 `t_classroom`, `t_classroom_material` 관련 migration이 적용되지 않음
- **Resolution**: `env=dev` 기준으로 current 확인, SQL preview, dry-run, 실제 migration, bootstrap smoke test까지 완료
- **Status**: Fixed

**Current Refactor Direction**
- 도메인 의미가 있는 규칙은 가능한 각 도메인 계층으로 이동
- 얇은 라우터 유지, 서비스는 유스케이스 단위로 작게 유지
- domain -> application DTO 의존 같은 경계 역전을 줄이는 리팩토링 진행 중
- 테스트 보강 작업은 TDD 기준으로 재정렬하고, 가능하면 기존 테스트는 보존한다

## Technical Debt
| Item | Impact | Priority | Mitigation |
|------|--------|----------|------------|
| 일부 라우터의 중복 응답 매핑 | 유지보수 비용 증가 | medium | 패턴을 더 점검하되 helper 남발 없이 정리 |
| 파일 저장소 side effect와 transaction 순서 | partial failure 위험 | high | `file` / `classroom_material` 흐름 재검토 |
| migration 수동 수정 기준 불명확 | 스키마 drift 재발 가능 | high | autogenerate 우선 규칙을 문서화하고 review 기준 확립 |

## Known Issues & Gotchas
- Alembic 기본 실행만 믿지 말고 항상 `-x env=...`를 함께 사용해야 올바른 설정이 로드된다.
- `upgrade --sql`은 preview일 뿐이며 실제 online 검증은 `-x dry-run upgrade`로 따로 해야 한다.
- DB 스키마 문제는 코드 버그처럼 보일 수 있으므로 500이 나와도 먼저 revision 상태를 확인한다.

## What Works Well
- `app/<domain>/domain|application|adapter` 구조는 확장 시 책임 분리가 잘 된다.
- `alembic/env.py`에 env 선택과 dry-run 지원을 넣어 로컬/테스트/개발 환경 migration이 예측 가능해졌다.
- bootstrap smoke test가 migration 이후 기본 실행 가능성을 빠르게 검증해 준다.

## Next Watch Items
- `file`와 `classroom_material`의 transaction + storage side effect 순서 재검토
- 남아 있는 중복 코드와 hexagonal 경계 위반 추가 정리
- AI 평가 도메인 확장 시 현재 구조 유지 가능성 점검

## 📂 Codebase References
- `alembic/env.py` - env 선택과 dry-run 지원
- `alembic/versions/a2d651fa6123_add_classroom_domain.py` - classroom schema 시작점
- `alembic/versions/daf876d85767_add_classroom_materials.py` - classroom material schema 추가
- `app/classroom/adapter/output/persistence/sqlalchemy/classroom.py` - 누락 테이블 오류가 관찰된 repository 경로
- `main.py` - migration 후 bootstrap smoke test 대상 앱 진입점

## Related Files
- `technical-domain.md` - 기술 운영 규칙과 구현 패턴
- `decisions-log.md` - 왜 이 migration 절차를 채택했는지에 대한 결정
- `business-tech-bridge.md` - 제품 요구와 현재 구조의 연결 배경
