<!-- Context: project-intelligence/nav | Priority: high | Version: 1.8 | Updated: 2026-03-28 -->

# Project Intelligence

**Purpose**: 이 프로젝트의 비즈니스와 기술 문맥을 빠르게 찾기 위한 진입점.
**Last Updated**: 2026-03-28

## Quick Routes
| What You Need | File | Description | Priority |
|---------------|------|-------------|----------|
| 제품의 목적과 사용자 이해 | `business-domain.md` | 교육 문제, 사용자, 시험 응시 시나리오 정리 | high |
| 구현 방식과 기술 패턴 이해 | `technical-domain.md` | 스택, 아키텍처, API 규칙, migration/TDD 운영 | critical |
| 비즈니스-기술 연결 확인 | `business-tech-bridge.md` | 제품 요구와 백엔드 구조 연결, 시험 API 경계 | high |
| 의사결정 배경 확인 | `decisions-log.md` | 주요 선택과 이유, TDD 원칙, 시험 API 정책 | high |
| 현재 상태와 이슈 확인 | `living-notes.md` | 최근 완료 작업, 다음 구현 우선순위, 기술 부채 | medium |

## Deep Dives
| File | When To Load |
|------|--------------|
| `technical-domain.md` | API 추가, 서비스 구현, 아키텍처/보안/도메인 규칙 및 migration 절차 파악 시 |
| `business-domain.md` | 요구사항 배경, 사용자 가치, 제품 운영 흐름이 필요할 때 |
| `business-tech-bridge.md` | 제품 가치가 왜 현재 구조로 구현되는지 확인할 때 |
| `decisions-log.md` | 기존 설계 선택을 유지하거나 변경할 때 |

## Loading Strategy
- 신규 참여자나 에이전트는 먼저 이 파일을 읽는다.
- 구현 작업 전에는 `technical-domain.md`를 우선 로드한다.
- 요구사항 해석이 필요한 작업이면 `business-domain.md`와 `business-tech-bridge.md`를 함께 읽는다.
- 설계 변경 전에는 `decisions-log.md`를 확인한다.

## 📂 Codebase References
- `.opencode/context/project-intelligence/technical-domain.md` - 실제 기술 패턴 기준 문서
- `.opencode/context/project-intelligence/business-domain.md` - 비즈니스 문맥 기준 문서
- `.opencode/context/core/standards/project-intelligence.md` - 프로젝트 인텔리전스 표준
- `.opencode/context/core/standards/project-intelligence-management.md` - 버전/갱신 규칙

## Related Files
- `technical-domain.md` - 기술 스택과 구현 패턴
- `business-domain.md` - 제품 목적과 사용자 맥락
- `decisions-log.md` - 변경 이력과 설계 배경
