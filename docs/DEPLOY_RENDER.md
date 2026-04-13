# Render 배포 가이드 (FastAPI)

## 1. 배포 대상

- 서비스 타입: `Web Service`
- 런타임: `Python`
- 브랜치: `main`

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
- `DATABASE_URL` (DB 사용하는 경우)
- `SECRET_KEY`
- `CORS_ORIGINS` (쉼표 구분 또는 JSON 배열 형태)

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
    plan: starter
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
