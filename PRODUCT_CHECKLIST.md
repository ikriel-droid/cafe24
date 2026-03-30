# ClaimMate AI Product Checklist

로컬 MVP 이후 실제 서비스 수준까지 가기 위한 작업 체크리스트입니다.

운영 규칙:
- 아직 안 끝난 항목은 `[ ]`
- 끝난 항목은 `[x]`
- 작업이 끝날 때마다 이 파일을 바로 갱신

## 0. Current Baseline

- [x] 로컬 MVP 실행 경로 정리
- [x] 인박스 / 상세 / 정책 / 대시보드 화면 구성
- [x] Mock AI 분류 / 답변 초안 생성
- [x] Mock Cafe24 sync / webhook / OAuth placeholder
- [x] 백엔드 테스트 / 프런트 빌드 / 로컬 실행 스크립트 정리

## 1. Live Cafe24 Integration

- [x] Cafe24 실제 OAuth authorize / callback / token exchange 구현
- [x] Cafe24 access token 저장 및 갱신 처리
- [x] Cafe24 주문 / 배송 / 클레임 실제 sync 구현
- [x] Cafe24 webhook 실제 엔드포인트 연결
- [x] webhook 서명 검증 및 위변조 방지
- [x] webhook 중복 수신 방지 키 처리
- [x] webhook 실패 재시도 정책 정리
- [ ] mock integration 상태를 실제 integration 상태 모델로 치환

## 2. Reply Delivery

- [ ] 실제 고객 응대 채널 발송 경로 결정
- [ ] 답변 발송 API 구현
- [ ] 발송 성공 / 실패 / 재시도 상태 모델 추가
- [ ] 발송 이력 상세 조회 화면 보강
- [ ] resend 정책 정의
- [ ] 발송 실패 큐 추가

## 3. Auth And Tenant Isolation

- [ ] 운영자 로그인 구현
- [ ] merchant 단위 데이터 격리
- [ ] 권한 / 역할 구분
- [ ] API 인증 / 세션 처리
- [ ] merchant별 정책 / 연동 설정 분리
- [ ] 감사 로그 열람 권한 제한

## 4. Background Jobs And Reliability

- [ ] Redis 기반 job queue 실제 사용
- [ ] sync 비동기 작업 분리
- [ ] webhook 처리 비동기화
- [ ] job retry / dead-letter 정책 추가
- [ ] 실시간 작업 상태 추적
- [ ] 운영자 재실행 버튼과 job 상태 연결

## 5. Database And Data Lifecycle

- [ ] Alembic migration 도입
- [ ] 운영용 PostgreSQL 스키마 정리
- [ ] seed data와 운영 데이터 분리
- [ ] soft delete / 보존 정책 정의
- [ ] 백업 / 복구 절차 문서화
- [ ] 샘플 데이터 초기화 명령 분리

## 6. AI Productionization

- [ ] OpenAI 실제 provider 구현
- [ ] prompt / system rule 관리 방식 정리
- [ ] merchant 정책 반영 프롬프트 개선
- [ ] AI 실패 시 deterministic fallback 정책 유지
- [ ] 모델 비용 / 토큰 사용량 기록
- [ ] 답변 품질 평가 기준 정리
- [ ] human review 기준 명확화

## 7. Operations UX

- [ ] 대시보드 KPI 최종 정의
- [ ] 운영자 메모 / 인수인계 UX 보강
- [ ] 감사 로그 검색 / 필터 추가
- [ ] 클레임 이력 diff 보기
- [ ] bulk action 지원 여부 결정
- [ ] SLA / 긴급도 기준 정리

## 8. Observability And Safety

- [ ] 구조화된 에러 로깅 추가
- [ ] API / webhook / job 메트릭 수집
- [ ] 알림 채널 연동
- [ ] rate limit / timeout / circuit breaker 정책
- [ ] 민감정보 마스킹 규칙 적용
- [ ] 관리자용 진단 페이지 추가

## 9. Deployment And Release

- [ ] production Docker image 정리
- [ ] 배포 환경변수 템플릿 정리
- [ ] staging / production 분리
- [ ] HTTPS / 도메인 / reverse proxy 구성
- [ ] CI build / test / deploy 파이프라인 추가
- [ ] 운영 문서 / 장애 대응 문서 정리

## 10. Commercial Readiness

- [ ] merchant onboarding 플로우
- [ ] 설치 가이드 / 운영 가이드 문서화
- [ ] 과금 기준 정의
- [ ] 사용량 측정 방식 설계
- [ ] 개인정보 처리 / 보관 정책 검토
- [ ] 베타 고객 검증 시나리오 확정
