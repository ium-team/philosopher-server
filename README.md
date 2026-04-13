# philosopher-server

`FastAPI` 기반 서버를 `Render`에 배포하는 것을 기준으로 팀 공통 기준을 정리한 저장소입니다.

## 문서 목록

- [아키텍처 가이드](./docs/ARCHITECTURE.md)
- [코드 컨벤션](./docs/CODE_CONVENTION.md)
- [Render 배포 가이드](./docs/DEPLOY_RENDER.md)
- [에이전트 작업 가이드](./AGENT.md)

## 권장 진행 순서

1. `docs/ARCHITECTURE.md`에서 기본 구조와 경계를 확정합니다.
2. `docs/CODE_CONVENTION.md`를 기준으로 첫 모듈부터 동일한 스타일을 적용합니다.
3. `docs/DEPLOY_RENDER.md` 기준으로 환경변수/배포 설정을 맞춥니다.
4. AI/자동화 도구를 함께 쓰는 경우 `AGENT.md`를 먼저 읽고 작업합니다.

## 이후 확장 문서 (선택)

- API 명세: OpenAPI 또는 API Blueprint
- 운영 문서: 배포/롤백/장애 대응 런북
- ADR: 주요 설계 결정 이력 관리

## 빠른 시작

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

서버 실행 후:

- Health check: `GET /health`
- V1 health: `GET /api/v1/health`
- Swagger UI: `GET /docs`
