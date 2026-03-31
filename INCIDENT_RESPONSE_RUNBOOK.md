# ClaimMate AI Incident Response Runbook

## 목적

운영 중 장애가 발생했을 때 확인 순서와 1차 대응 기준을 정리합니다.

## 우선 확인 페이지

- 앱 health: `/health`
- 관리자 진단: `/admin/diagnostics`
- Cafe24 콘솔: `/integrations/cafe24`

## 장애 분류

### 1. API 장애

징후:
- `/health` 실패
- 5xx 증가
- 로그인 불가

1차 대응:
1. 컨테이너 상태 확인
2. `/admin/diagnostics`의 recent errors 확인
3. reverse proxy와 API 로그 확인
4. 최근 배포 여부 확인

### 2. Cafe24 webhook 적체

징후:
- pending webhook 증가
- failed webhook 증가
- health 상태가 `attention`

1차 대응:
1. `/admin/diagnostics`에서 webhook/job metrics 확인
2. dead letter job 유무 확인
3. Cafe24 console에서 retry action 실행
4. 서명 secret, rate limit, circuit breaker 상태 확인

### 3. Background job 장애

징후:
- retry_scheduled, dead_letter 증가
- sync 결과 반영 지연

1차 대응:
1. diagnostics의 recent jobs 확인
2. dead letter 원인 메시지 확인
3. Redis 연결 확인
4. 필요하면 manager 권한으로 process-pending 수동 실행

### 4. AI / 외부 API 장애

징후:
- OpenAI fallback 증가
- Cafe24 live sync 실패
- reply delivery webhook 실패

1차 대응:
1. diagnostics의 circuit breaker 상태 확인
2. timeout/alert 발생 여부 확인
3. fallback은 허용하되, 실패율이 높으면 외부 provider 키와 네트워크 상태 확인

## 즉시 완화책

- reply delivery 실패: resend 또는 manual_handoff로 임시 전환
- OpenAI 장애: mock fallback 유지, review_required 기준으로 운영
- Cafe24 webhook 실패: retry queue 처리 후 지속되면 live webhook 일시 중지 검토
- 배포 직후 장애: 이전 이미지 태그로 롤백

## 장애 기록 원칙

장애 대응 후 아래를 남깁니다.
- 발생 시각
- 영향 범위
- root cause 추정
- 완화 조치
- 재발 방지 액션

이 기록은 추후 `## 9. Deployment And Release` 및 `## 10. Commercial Readiness` 문서화에 다시 반영합니다.
