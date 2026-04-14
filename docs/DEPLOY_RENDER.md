# Render 배포 가이드 (FastAPI)

## 1. 배포 대상

- 서비스 타입: `Web Service`
- 런타임: `Python`
- 브랜치: `main`
- Render 플랜: `free`

## 2. 기본 명령

- Build Command:
```bash
pip install -r requirements.txt
```

- Start Command:
```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## 3. 필수 환경 변수

- `ENV=prod`
- `PORT` (Render에서 자동 주입)
- `DATABASE_URL` (Supabase Postgres 연결 문자열)
- `SUPABASE_URL` (예: `https://<project-ref>.supabase.co`)
- `SUPABASE_JWT_AUDIENCE` (기본값 `authenticated`)
- `SUPABASE_JWT_SECRET` (`HS256` 토큰 검증을 사용할 때 필수)
- `OPENAI_API_KEY` (철학자 답변 생성에 필수)
- `SECRET_KEY`
- `CORS_ORIGINS` (쉼표 구분 또는 JSON 배열 형태)

Supabase 권장값:

- 앱 서버는 Supabase `pooler` 연결 문자열 우선 사용
- 쿼리 파라미터에 `sslmode=require` 포함
- SQLAlchemy(sync) 기준 DSN 예시:

```text
postgresql+psycopg://postgres.<project-ref>:<password>@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres?sslmode=require
```

JWT 검증 방식:

- `RS256/ES256`(JWKS) 토큰이면 `SUPABASE_URL`만으로 검증 가능
- `HS256` 토큰이면 `SUPABASE_JWT_SECRET`를 함께 설정해야 함

## 4. Health Check

- 경로: `/health`
- 기대 응답: `200 OK`

Render Health Check Path에 `/health`를 설정합니다.

## 5. 배포 전 체크리스트

- [ ] `requirements.txt` 최신화
- [ ] `uvicorn app.main:app` 기준으로 앱 진입점 일치
- [ ] 환경 변수 누락 없음
- [ ] DB 마이그레이션 전략 준비 (배포 전/후)
- [ ] `/health` 엔드포인트 동작 확인

## 6. render.yaml (선택)

루트에 `render.yaml`을 두면 IaC 방식으로 관리할 수 있습니다.

```yaml
services:
  - type: web
    name: philosopher-server
    runtime: python
    plan: free
    branch: main
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /health
    envVars:
      - key: ENV
        value: prod
      - key: SECRET_KEY
        sync: false
      - key: DATABASE_URL
        sync: false
```
