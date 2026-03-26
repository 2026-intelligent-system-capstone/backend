<!-- Context: project-intelligence/bridge | Priority: high | Version: 1.1 | Updated: 2026-03-25 -->

# Business ↔ Tech Bridge

**Purpose**: 제품 요구가 현재 백엔드 구조와 어떻게 연결되는지 빠르게 설명하는 문서.
**Last Updated**: 2026-03-25

## Quick Reference
- **Business Goal**: 대화형 AI 평가를 통해 학습 이해도와 사고 과정을 진단한다.
- **Technical Base**: FastAPI + Hexagonal Architecture + DI + PostgreSQL + Valkey
- **Current Focus**: 운영 기반(조직, 인증, 강의실, 자료) 위에 평가 기능을 확장할 준비를 한다.
- **Update When**: 핵심 기능 출시, 사용자 흐름 변경, 아키텍처 결정 변경

## Core Mapping
| Business Need | Technical Solution | Why This Mapping | Business Value |
|---------------|-------------------|------------------|----------------|
| 학교 단위 사용자 식별 | 조직 + 학교 연동 로그인 + 쿠키 인증 | 대학 운영 구조를 그대로 반영해야 함 | 실제 교육 현장 도입 가능성 확보 |
| 교수 중심 수업 운영 | 강의실, 학생 초대, 자료 관리 도메인 | 평가 이전에 수업/소속 맥락이 먼저 필요함 | 시험 대상과 범위를 안정적으로 관리 |
| 학생별 접근 제어 | 서비스 계층에서 조직/역할/소유권 재검증 | 시험/자료 노출 범위가 잘못되면 신뢰가 무너짐 | 권한 오류와 정보 노출 위험 감소 |
| 심층 평가 확장 기반 | Request-Command-UseCase 구조와 도메인 분리 | AI 평가 기능이 추가되어도 운영 기능과 분리 가능 | 기능 확장 시 변경 영향 최소화 |
| 지속 가능한 평가 경험 | 테스트 가능한 구조 + CI 검증 + 공통 예외 흐름 | 교육 서비스는 예측 가능성과 안정성이 중요함 | 운영 안정성, 변경 신뢰성 확보 |

## Feature Mapping
**Feature: 학교 연동 로그인과 역할 기반 접근**
- **Business**: 학생과 교수/관리자를 구분하고 학교 소속 기준으로 서비스를 사용해야 한다.
- **Tech**: `Organization`, `Auth`, `User` 도메인과 학교 연동 adapter, 쿠키 기반 JWT 인증으로 구현한다.
- **Connection**: 서비스의 첫 진입점에서 소속과 역할을 확정해야 이후 강의실, 자료, 시험 권한이 일관되게 동작한다.

**Feature: 교수자 중심 강의실 운영**
- **Business**: 교수자는 강의실을 만들고 학생을 초대하며 평가 범위를 관리해야 한다.
- **Tech**: `ClassroomService`가 조직, 교수/학생 역할, 관리 권한을 검증하고 라우터는 입력/응답 변환만 담당한다.
- **Connection**: 강의실은 시험과 자료 공개 범위를 결정하는 기본 단위라서, 운영 규칙이 먼저 안정되어야 평가 경험도 설계할 수 있다.

**Feature: 강의자료 공개 범위 제어**
- **Business**: 학생이 모든 자료를 보는 것이 아니라 허용된 강의실 자료만 접근해야 한다.
- **Tech**: `ClassroomMaterialService`가 강의실 접근성과 `allow_student_material_access`를 함께 확인한다.
- **Connection**: 자료 공개 범위는 시험 범위와 직접 연결되므로, 단순 파일 업로드가 아니라 학습/평가 정책을 담는 기능이다.

**Feature: 향후 AI 심층 평가 확장**
- **Business**: 학생 답변을 바탕으로 꼬리질문, 리포트, 학습 분석으로 이어져야 한다.
- **Tech**: 현재 백엔드는 유스케이스 중심 서비스와 도메인 분리 구조를 채택해 평가 엔진, 리포트, 분석 도메인을 추가하기 쉽게 만든다.
- **Connection**: 운영 기반과 평가 엔진을 분리하면 AI 기능이 커져도 인증/강의실/자료 규칙을 흔들지 않고 확장할 수 있다.

## Trade-offs
| Situation | Decision Made | Why |
|-----------|---------------|-----|
| 라우터에 빠르게 규칙 추가 가능 | 라우터는 얇게 유지하고 서비스/도메인에 규칙 배치 | 권한, 조직, 자원 규칙을 테스트 가능하게 유지하기 위해 |
| 공통 로직을 `core/`에 모으기 쉬움 | 도메인 의미가 있으면 각 도메인에 남김 | 교육 정책이 기술 유틸로 희석되는 것을 막기 위해 |
| 토큰만으로 인증 처리 가능 | refresh token을 Valkey에 저장해 회전 관리 | 로그아웃, 재발급, 무효화를 안정적으로 지원하기 위해 |

## Common Misalignments
- **평가 기능만 먼저 구현**: 운영 맥락 없이 시험만 만들면 대상/범위/권한이 불안정해진다.
- **공통화 과도**: 교육 도메인 규칙을 `core/`로 밀어 넣으면 정책 변경 추적이 어려워진다.
- **권한 체크를 라우터에만 배치**: 서비스 재검증이 없으면 조직 간 접근 누수가 생길 수 있다.

## 📂 Codebase References
- `app/auth/application/service/auth.py` - 학교 단위 로그인과 토큰 발급/회전
- `app/organization/adapter/output/integration/hansung.py` - 실제 학교 시스템 연동
- `app/classroom/application/service/classroom.py` - 강의실 운영과 조직/역할 검증
- `app/classroom_material/application/service/classroom_material.py` - 자료 공개 범위와 학생 접근 규칙
- `app/classroom/adapter/input/api/v1/classroom.py` - 얇은 라우터 + 유스케이스 연결 패턴
- `tests/app/auth/application/test_auth_service.py` - 인증 비즈니스 규칙 검증
- `tests/app/classroom/adapter/input/test_classroom_api.py` - 역할별 강의실 관리 흐름 검증

## Related Files
- `business-domain.md` - 사용자, 가치, 제품 시나리오
- `technical-domain.md` - 구현 패턴과 아키텍처 규칙
- `decisions-log.md` - 추후 남길 주요 트레이드오프 기록
