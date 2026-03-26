<!-- Context: project-intelligence/business | Priority: high | Version: 1.1 | Updated: 2026-03-25 -->

# Business Domain

**Purpose**: 이 프로젝트가 해결하려는 교육 문제, 사용자 가치, 핵심 운영 시나리오를 빠르게 이해하기 위한 문서.
**Last Updated**: 2026-03-25

## Quick Reference
- **Product**: 대화형 AI 기반 학습 역량 평가 플랫폼
- **Primary Users**: 대학생, 교수/관리자
- **Core Value**: 정답 여부만이 아니라 이해도와 사고 과정을 대화형으로 평가
- **Update When**: PRD 변경, 역할/평가 흐름 변경, 핵심 기능 우선순위 변경

## Project Identity
**Project Name**: 대화형 AI 기반 학습 역량 평가 플랫폼
**Tagline**: AI와의 심층 대화로 학습 역량을 진단하고 피드백하는 평가 시스템
**Problem Statement**: 기존 객관식·단답형 중심 평가는 학생의 실제 이해도, 문제 해결 과정, 비판적 사고를 충분히 측정하지 못한다.
**Solution**: 학생 답변을 실시간 분석해 후속 심층 질문을 생성하고, 결과를 리포트와 학습 분석으로 연결한다.

## Target Users
| User Segment | Who They Are | What They Need | Pain Points |
|--------------|--------------|----------------|-------------|
| 학생 | 자기주도 학습을 원하는 대학생 | 심층 평가, 즉시 피드백, 학습 진단 | 암기식 평가, 피드백 부족, 약점 파악 어려움 |
| 교수/관리자 | 평가와 수업 운영을 담당하는 교수진 | 강의실 운영, 평가 생성, 리포트 조회 | 주관식 평가 부담, 학생별 이해도 파악 어려움 |

## Core Value
- 학생 답변 맥락에 따라 질문이 이어지는 `심층 대화형 평가`를 제공한다.
- 평가 결과를 강점/약점/개선 방향이 포함된 리포트로 전환한다.
- 교수자는 루브릭, 시험 범위 자료, 학생별 결과를 바탕으로 수업을 개선할 수 있다.
- 학교 연동 로그인과 역할 기반 접근 제어로 실제 대학 운영 흐름과 맞춘다.

## Major Product Areas
| Area | Business Intent | Current Product Shape |
|------|-----------------|-----------------------|
| AI 심층 평가 | 사고 과정과 이해도 평가 | 연속 꼬리질문, 품질 가드레일, 선택적 RAG |
| 리포트/분석 | 평가 결과를 학습 개선으로 연결 | 학생 피드백, 교수자 통합 분석, 대시보드 |
| 인증/권한 | 학교 단위 사용자 구분과 접근 제어 | 학교 선택 로그인, 역할별 메뉴/기능 제한 |
| 강의실 운영 | 교수자 중심 수업/평가 운영 | 강의실, 학생 초대, 자료 관리, 평가 관리 |
| 시험 응시 | 학생이 실제 평가를 완료하게 함 | 시험 목록, 대화형 응시, TTS/STT, 결과 조회 |

## Representative Scenario
대학생은 로그인 후 자신에게 배정된 시험을 시작한다. AI는 첫 질문 이후 학생 답변을 분석해 근거, 반례, 한계, 적용을 묻는 후속 질문을 이어간다. 평가가 끝나면 학생은 강점/약점과 개선 방향을 확인하고, 교수자는 학생별 리포트와 통합 분포를 통해 수업 보완 포인트를 본다.

## Success Metrics
| Metric | Definition | Why It Matters |
|--------|------------|----------------|
| WAU/MAU | 주간/월간 활성 사용자 수 | 실제 학습 도구로 정착했는지 확인 |
| 평가 완료율 | 시작 대비 완료 비율 | 사용자 경험과 시험 흐름의 완성도 확인 |
| 학습 만족도 | 설문 기반 만족도 | 피드백과 질문 품질의 체감 가치 측정 |
| 진단 정확도 | AI 결과와 실제 성과 상관 | 평가 신뢰도 검증 |
| 재방문율 | 일정 기간 내 재응시 비율 | 반복 학습 도구로서의 지속성 확인 |

## Risks & Constraints
- AI 질문/평가 정확도가 낮으면 플랫폼 신뢰가 무너진다.
- 학생 평가 데이터와 결과는 교육 데이터이므로 보안과 개인정보 보호가 중요하다.
- 학교 종합정보시스템 연동은 외부 시스템 가용성과 정책에 영향을 받는다.
- 멀티 에이전트, RAG, 대화형 시험 UX를 함께 다뤄 구현 복잡도가 높다.
- 새로운 평가 방식에 대한 교수진과 학생의 적응 비용이 존재한다.

## Current Product Direction
- 학생과 교수자의 역할을 분리해 기능 트리를 재구성한 상태다.
- 백엔드는 이미 조직, 사용자, 인증, 강의실, 강의자료 도메인을 중심으로 운영 기반을 먼저 만들고 있다.
- 앞으로 AI 심층 평가 엔진, 시험 응시 경험, 리포트 분석이 이 운영 기반 위에 확장될 가능성이 높다.

## 📂 Codebase References
**Business Logic**:
- `app/classroom/application/service/classroom.py` - 강의실 생성, 초대, 접근 제어 규칙
- `app/classroom_material/application/service/classroom_material.py` - 강의자료 공개 범위와 학생 접근 규칙
- `app/auth/application/service/auth.py` - 학교 단위 로그인과 토큰 발급 흐름

**Implementation**:
- `app/classroom/adapter/input/api/v1/classroom.py` - 교수자 운영 강의실 API
- `app/classroom_material/adapter/input/api/v1/classroom_material.py` - 강의자료 업로드/조회 API
- `app/organization/adapter/input/api/v1/organization.py` - 학교(조직) 관리 API
- `app/organization/adapter/output/integration/hansung.py` - 한성대 종합정보시스템 로그인 연동

**Tests**:
- `tests/app/classroom/adapter/input/test_classroom_api.py` - 역할별 강의실 접근/관리 검증
- `tests/app/classroom_material/adapter/input/test_classroom_material_api.py` - 학생/교수 자료 접근 검증
- `tests/app/auth/adapter/input/test_auth_api.py` - 쿠키 기반 인증 흐름 검증
- `tests/app/organization/adapter/output/integration/test_hansung.py` - 학교 연동 인증 시나리오 검증

## Related Files
- `technical-domain.md` - 비즈니스 요구를 받치는 기술 구조와 구현 패턴
- `business-tech-bridge.md` - 제품 목표와 기술 설계의 연결
- `decisions-log.md` - 제품/설계 선택의 배경
