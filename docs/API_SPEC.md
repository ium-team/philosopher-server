# API 명세 (v1)

## 1. 개요

- 서비스명: `philosopher-server`
- 프레임워크: `FastAPI`
- API 버전 Prefix: `/api/v1`
- 문서 기준일: `2026-04-13`

기본적으로 헬스체크 엔드포인트는 아래 2개를 제공합니다.

- 루트 헬스체크: `GET /health`
- v1 헬스체크: `GET /api/v1/health`

## 2. 공통 규약

- 콘텐츠 타입: `application/json`
- 인증: 현재 없음
- 공통 응답 포맷: 현재는 엔드포인트별 단순 JSON 응답 사용

## 3. 엔드포인트 명세

### 3.1 `GET /health`

서비스 기본 상태를 확인하는 헬스체크 엔드포인트입니다.

- Method: `GET`
- Path: `/health`
- Request Body: 없음
- Query Parameter: 없음
- Header: 없음

성공 응답:

- Status Code: `200 OK`
- Body:

```json
{
  "status": "ok"
}
```

오류 응답:

- 현재 구현 기준 커스텀 오류 스키마 없음 (FastAPI 기본 오류 포맷 사용)

`curl` 예시:

```bash
curl -X GET http://localhost:8000/health
```

### 3.2 `GET /api/v1/health`

버전 라우터(`/api/v1`) 기준 서비스 상태를 확인하는 헬스체크 엔드포인트입니다.

- Method: `GET`
- Path: `/api/v1/health`
- Request Body: 없음
- Query Parameter: 없음
- Header: 없음

성공 응답:

- Status Code: `200 OK`
- Body:

```json
{
  "status": "ok"
}
```

오류 응답:

- 현재 구현 기준 커스텀 오류 스키마 없음 (FastAPI 기본 오류 포맷 사용)

`curl` 예시:

```bash
curl -X GET http://localhost:8000/api/v1/health
```

## 4. 자동 생성 OpenAPI 문서

FastAPI 기본 문서 경로는 아래와 같습니다.

- Swagger UI: `GET /docs`
- ReDoc: `GET /redoc`
- OpenAPI JSON: `GET /openapi.json`

## 5. 버전 정책

- 현재 버전: `v1`
- 하위 호환성을 깨는 변경은 신규 버전 Prefix(예: `/api/v2`)로 분리합니다.

## 6. 변경 이력

- `2026-04-13`: 최초 작성
