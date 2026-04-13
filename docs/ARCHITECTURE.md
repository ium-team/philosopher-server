# FastAPI 서버 아키텍처 가이드

## 1. 목표

- 변경에 강한 구조를 유지한다.
- 장애 원인 추적이 가능한 관측성을 기본값으로 둔다.
- 도메인 로직과 인프라 의존성을 분리한다.

## 2. 아키텍처 원칙

- `도메인 우선`: 핵심 비즈니스 규칙은 프레임워크 바깥에 둔다.
- `단방향 의존`: 상위 계층(도메인)은 하위 계층(인프라)을 모른다.
- `명시적 계약`: 계층 간 DTO/인터페이스를 문서화하고 버전 관리한다.
- `실패 우선 설계`: 예외/타임아웃/재시도를 정상 흐름처럼 설계한다.

## 3. 권장 계층 구조 (FastAPI)

아래 구조를 기본값으로 사용합니다.

```text
app/
  main.py                    # FastAPI 앱 진입점
  api/
    v1/
      routers/               # 라우터(엔드포인트 정의)
      schemas/               # 요청/응답 Pydantic 스키마
  domain/                    # 엔티티, 값 객체, 도메인 서비스
  application/               # 유스케이스, 트랜잭션 경계
  infrastructure/
    db/                      # SQLAlchemy 세션, 모델, 리포지토리 구현
    external/                # 외부 API/스토리지 어댑터
  core/                      # 설정, 보안, 로깅, 예외 핸들러
tests/
  unit/
  integration/
  e2e/
```

## 4. 요청 처리 흐름

1. FastAPI 라우터에서 인증/인가/검증을 수행한다.
2. `application` 유스케이스가 트랜잭션 경계를 연다.
3. 유스케이스가 `domain` 모델을 호출해 비즈니스 규칙을 실행한다.
4. 영속성/외부 연동은 `infrastructure` 포트를 통해 수행한다.
5. 응답은 Pydantic 스키마로 직렬화한다.

## 5. 데이터/트랜잭션 기준

- 트랜잭션은 유스케이스 단위로 짧게 유지한다.
- N+1, 락 경합이 발생하는 쿼리는 초기에 성능 기준을 정의한다.
- 마이그레이션은 항상 롤백 경로를 준비한다.
- 읽기/쓰기 분리가 필요하면 CQRS를 부분 도입한다.

## 6. 에러 처리 기준

- 도메인 에러와 시스템 에러를 분리한다.
- 외부 노출 에러 포맷은 일관된 스키마를 사용한다.
- 예외 메시지에 민감 정보(토큰, 비밀번호, 내부 경로)를 포함하지 않는다.

권장 에러 응답 예시:

```json
{
  "code": "RESOURCE_NOT_FOUND",
  "message": "요청한 리소스를 찾을 수 없습니다.",
  "requestId": "7e5f0a8d-2e7a-4a2a-95c0-a7e3f5c9f001"
}
```

## 7. 관측성(Observability)

- 모든 요청에 `requestId`를 부여한다.
- 구조화 로그(JSON) + 로그 레벨(`debug/info/warn/error`)을 표준화한다.
- 핵심 메트릭: 지연시간(p95/p99), 오류율, 외부 의존성 실패율.
- 분산 추적(Trace)을 도입할 경우 서비스 경계를 넘는 호출에 trace context를 전달한다.

## 8. 보안 기준

- 비밀값은 코드/레포에 저장하지 않는다.
- 입력 검증은 경계(`interfaces`)에서 수행한다.
- 권한 검사는 핸들러와 도메인 규칙에서 이중 방어한다.
- 감사 로그가 필요한 이벤트(권한 변경, 결제, 관리자 기능)는 별도 기록한다.

## 9. 설정 관리

- `pydantic-settings`로 환경 변수를 타입 검증 후 로드한다.
- 실행 프로필(`local`, `dev`, `staging`, `prod`)을 분리한다.
- 필수 설정 누락 시 서버는 즉시 실패(fail-fast)한다.

## 10. 확정 기술 스택

- 언어/런타임: `Python 3.12` (권장)
- 웹 프레임워크: `FastAPI`
- ASGI 서버: `Uvicorn` (Render start command에서 사용)
- 데이터 검증: `Pydantic v2`
- ORM/DB: `SQLAlchemy 2.x` + `Alembic`
- 배포 플랫폼: `Render Web Service`

## 11. Render 운영 기준

- 프로세스는 단일 컨테이너 내 `uvicorn` 프로세스로 시작한다.
- Health check 엔드포인트(`/health`)를 반드시 제공한다.
- 환경 변수는 Render Dashboard에서 관리한다.
- 배포 시 마이그레이션 필요하면 `preDeployCommand` 또는 별도 잡으로 실행한다.
