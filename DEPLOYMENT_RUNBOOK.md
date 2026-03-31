# ClaimMate AI Deployment Runbook

## 목적

이 문서는 ClaimMate AI를 staging / production 환경에 배포할 때 필요한 준비물, 이미지 릴리스, compose 기동, reverse proxy, 롤백 기준을 정리합니다.

## 배포 자산

- staging compose: [deploy/docker-compose.staging.yml](c:\Users\Administrator\.vscode\cli\cafe24\claimmate-ai\deploy\docker-compose.staging.yml)
- production compose: [deploy/docker-compose.production.yml](c:\Users\Administrator\.vscode\cli\cafe24\claimmate-ai\deploy\docker-compose.production.yml)
- staging env 예시: [deploy/.env.staging.example](c:\Users\Administrator\.vscode\cli\cafe24\claimmate-ai\deploy\.env.staging.example)
- production env 예시: [deploy/.env.production.example](c:\Users\Administrator\.vscode\cli\cafe24\claimmate-ai\deploy\.env.production.example)
- staging nginx: [deploy/nginx/claimmate.staging.conf](c:\Users\Administrator\.vscode\cli\cafe24\claimmate-ai\deploy\nginx\claimmate.staging.conf)
- production nginx: [deploy/nginx/claimmate.production.conf](c:\Users\Administrator\.vscode\cli\cafe24\claimmate-ai\deploy\nginx\claimmate.production.conf)

## 사전 준비

1. 서버에 Docker Engine + Docker Compose plugin 설치
2. DNS 준비
   - staging: `staging.claimmate.example.com`
   - production: `claimmate.example.com`
3. TLS 인증서 배치
   - `deploy/certs/fullchain.pem`
   - `deploy/certs/privkey.pem`
4. Cafe24, OpenAI, alert webhook, reply delivery webhook 비밀값 준비

## 이미지 릴리스

GitHub Actions의 `claimmate-release` workflow를 사용합니다.

1. `release_tag` 입력
   예: `2026-03-31-01`
2. `environment` 선택
   - `staging`
   - `production`
3. workflow가 GHCR에 아래 이미지를 푸시
   - `ghcr.io/<owner>/claimmate-ai-api:<tag>`
   - `ghcr.io/<owner>/claimmate-ai-web:<tag>`
4. 동시에 deploy bundle artifact 생성

## Staging 배포

1. env 파일 준비
```powershell
Copy-Item deploy\.env.staging.example deploy\.env.staging
```

2. 이미지 태그와 비밀값 채우기

3. compose 기동
```powershell
docker compose --env-file deploy/.env.staging -f deploy/docker-compose.staging.yml pull
docker compose --env-file deploy/.env.staging -f deploy/docker-compose.staging.yml up -d
```

4. 확인
- `https://staging.claimmate.example.com/health`
- `https://staging.claimmate.example.com/admin/diagnostics`
- `docker compose --env-file deploy/.env.staging -f deploy/docker-compose.staging.yml ps`

## Production 배포

1. env 파일 준비
```powershell
Copy-Item deploy\.env.production.example deploy\.env.production
```

2. 이미지 태그와 비밀값 채우기

3. 배포
```powershell
docker compose --env-file deploy/.env.production -f deploy/docker-compose.production.yml pull
docker compose --env-file deploy/.env.production -f deploy/docker-compose.production.yml up -d
```

4. smoke check
- `/health`
- `/api/auth/session` expected 401 when unauthenticated
- manager 로그인 후 `/admin/diagnostics`
- Cafe24 console 상태

## 마이그레이션

API 컨테이너에서 Alembic 적용:

```powershell
docker compose --env-file deploy/.env.production -f deploy/docker-compose.production.yml exec api alembic upgrade head
```

배포 전후 모두 `head` 기준 일치 여부 확인이 필요합니다.

## 롤백

1. 이전 release tag로 `CLAIMMATE_API_IMAGE`, `CLAIMMATE_WEB_IMAGE` 변경
2. 동일 compose 명령으로 다시 `up -d`
3. 필요 시 DB migration 롤백 여부는 별도 검토
   - 스키마 변경이 포함된 릴리스는 사전 백업 없이 즉시 롤백하지 않음

## 배포 판단 기준

- API health 정상
- `/admin/diagnostics` 진입 가능
- dead letter jobs 증가 없음
- 5xx 급증 없음
- Cafe24 live connection 상태가 비정상으로 변하지 않음
