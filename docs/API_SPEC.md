# API 명세 (v1)

## 1. 개요

- 서비스명: `philosopher-server`
- 프레임워크: `FastAPI`
- API 버전 Prefix: `/api/v1`
- 문서 기준일: `2026-04-14`

## 2. 공통 규약

- 콘텐츠 타입: `application/json`
- 인증: `/api/v1` 하위 대부분 엔드포인트는 `Authorization: Bearer <Supabase Access Token>` 필요
- JWT 검증: Supabase JWKS 기반 서명 검증, `RS256`/`ES256` 알고리즘 허용
- 공통 응답 포맷: 현재는 엔드포인트별 단순 JSON 응답 사용
- 사용자 격리: 프로젝트/대화/메시지는 토큰의 `sub`(user id) 기준으로 분리 저장

## 3. 엔드포인트 명세

### 3.1 `GET /health`

성공 응답:

```json
{
  "status": "ok"
}
```

### 3.2 `GET /api/v1/health`

성공 응답:

```json
{
  "status": "ok"
}
```

### 3.3 `GET /api/v1/me`

현재 로그인한 사용자 정보를 반환합니다.

성공 응답:

```json
{
  "id": "b6450d8d-1748-4364-8a1a-6e6ce6d8ce64",
  "email": "user@example.com",
  "role": "authenticated"
}
```

### 3.4 `POST /api/v1/chat/projects`

사용자 프로젝트를 생성합니다.

요청:

```json
{
  "name": "윤리학 프로젝트",
  "description": "도덕 철학 대화",
  "instruction": "항상 핵심 요약 3줄을 마지막에 추가"
}
```

### 3.5 `GET /api/v1/chat/projects`

현재 사용자 프로젝트 목록을 반환합니다.

- 기본 프로젝트(`is_default=true`)는 내부 개념으로만 사용되며 목록에 노출되지 않습니다.
- 목록 정렬: `updated_at` 내림차순, `created_at` 내림차순

### 3.6 `PATCH /api/v1/chat/projects/{project_id}/settings`

프로젝트 설정을 수정합니다.

요청(필드 중 최소 1개 필요):

```json
{
  "name": "윤리학 프로젝트 v2",
  "instruction": "답변 전에 반례를 먼저 검토해"
}
```

### 3.7 `POST /api/v1/chat/conversations`

일반 채팅용 대화를 생성합니다.

- 서버는 사용자별 기본 프로젝트(숨김)를 내부적으로 생성/재사용하며, 사용자는 기본 프로젝트를 직접 볼 필요가 없습니다.

요청:

```json
{
  "philosopher": "socrates",
  "title": "일반 채팅"
}
```

### 3.8 `POST /api/v1/chat/projects/{project_id}/conversations`

특정 프로젝트에 철학자 대화를 생성합니다.

요청:

```json
{
  "philosopher": "socrates",
  "title": "정의란 무엇인가"
}
```

- `philosopher` 허용값: `socrates`, `nietzsche`, `hannah_arendt`

### 3.9 `GET /api/v1/chat/projects/{project_id}/conversations`

프로젝트 단위 대화 목록을 조회합니다.

### 3.10 `PATCH /api/v1/chat/conversations/{conversation_id}/project`

대화의 소속 프로젝트를 변경합니다(프로젝트 이동).
- `project_id`가 `null`이면 사용자 기본 프로젝트(숨김)로 이동합니다.

요청:

```json
{
  "project_id": "target-project-id"
}
```

### 3.11 `POST /api/v1/chat/conversations/{conversation_id}/messages`

사용자 메시지를 저장하고, 선택된 철학자 페르소나로 AI 응답을 생성해 함께 저장합니다.

요청:

```json
{
  "content": "정의는 배울 수 있는가?"
}
```

성공 응답:

```json
{
  "user_message": {
    "id": "...",
    "role": "user",
    "content": "정의는 배울 수 있는가?",
    "created_at": "2026-04-13T14:21:00.000000Z"
  },
  "assistant_message": {
    "id": "...",
    "role": "assistant",
    "content": "...",
    "created_at": "2026-04-13T14:21:01.000000Z"
  }
}
```

주요 오류 응답:

- `404`: 다른 사용자 소유 대화 또는 존재하지 않는 대화 (`Conversation not found`)
- `503`: `OPENAI_API_KEY` 누락 (`OPENAI_API_KEY is not configured`)
- `502`: OpenAI 호출 실패/빈 응답

### 3.12 `GET /api/v1/chat/conversations/{conversation_id}/messages`

대화 메시지 히스토리를 시간순으로 조회합니다.

### 3.13 `DELETE /api/v1/chat/conversations/{conversation_id}`

대화 1개를 삭제합니다.

- 본인 소유 대화만 삭제할 수 있습니다.
- 삭제 성공 시 `204 No Content`를 반환합니다.
- 대화에 속한 메시지는 함께 삭제됩니다.

주요 오류 응답:

- `404`: 다른 사용자 소유 대화 또는 존재하지 않는 대화 (`Conversation not found`)

### 3.14 `DELETE /api/v1/chat/projects/{project_id}`

프로젝트 1개를 삭제합니다.

- 본인 소유 일반 프로젝트만 삭제할 수 있습니다.
- 기본 프로젝트(`is_default=true`)는 삭제 대상이 아닙니다.
- 삭제 성공 시 `204 No Content`를 반환합니다.
- 프로젝트에 속한 대화와 메시지는 모두 함께 삭제됩니다.

주요 오류 응답:

- `404`: 다른 사용자 소유 프로젝트 또는 존재하지 않는 프로젝트 (`Project not found`)

## 4. 환경 변수

- `DATABASE_URL`: 미설정 시 `sqlite:///./.local/philosopher.db` 사용
- `OPENAI_API_KEY`: 철학자 AI 응답 생성에 필요
- 모델은 서버에서 `gpt-4o-mini`로 고정

## 5. AI 연동 정책

- OpenAI API: `POST /v1/responses`
- 모델: `gpt-4o-mini` (환경변수로 변경 불가)
- 철학자 시스템 프롬프트는 서버에서 고정 관리:
  - `socrates`
  - `nietzsche`
  - `hannah_arendt`
- 프로젝트에 `instruction`이 설정된 경우, 철학자 시스템 프롬프트 뒤에 결합되어 대화 생성에 반영됩니다.

## 6. 자동 생성 OpenAPI 문서

- Swagger UI: `GET /docs`
- ReDoc: `GET /redoc`
- OpenAPI JSON: `GET /openapi.json`

## 7. 버전 정책

- 현재 버전: `v1`
- 하위 호환성을 깨는 변경은 신규 버전 Prefix(예: `/api/v2`)로 분리합니다.

## 8. 변경 이력

- `2026-04-13`: 헬스체크/인증 API 추가
- `2026-04-13`: 프로젝트/철학자 대화/메시지 저장 API 추가
- `2026-04-13`: OpenAI 모델 `gpt-4o-mini` 고정 정책 반영
- `2026-04-14`: 프로젝트 이동/설정 수정 API 추가
- `2026-04-14`: 일반 채팅용 기본 프로젝트(숨김) 개념 도입
- `2026-04-14`: 프로젝트 지침(`instruction`) AI 반영
- `2026-04-14`: 프로젝트 삭제/대화 삭제 API 추가
