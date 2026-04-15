from __future__ import annotations

from typing import Any

import httpx
from fastapi.testclient import TestClient

from app.api.v1.dependencies.auth import get_current_user_claims
from app.application.services.tts import (
    InMemoryRateLimiter,
    TTSServiceError,
    VoiceProfile,
    _call_tts_provider,
    synthesize_philosopher_tts,
)
from app.infrastructure.db.models import Philosopher
from app.main import app

client = TestClient(app)


def _set_user(user_id: str) -> None:
    app.dependency_overrides[get_current_user_claims] = lambda: {
        "sub": user_id,
        "email": f"{user_id}@example.com",
        "role": "authenticated",
    }


def test_tts_returns_audio_mpeg_binary(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _set_user("tts-user")
    captured: dict[str, Any] = {}

    def _mock_synthesize(philosopher_id, text, rate_limit_key, limiter):  # type: ignore[no-untyped-def]
        captured["philosopher_id"] = philosopher_id
        captured["text"] = text
        captured["rate_limit_key"] = rate_limit_key
        return b"ID3\x00\x00mock-audio"

    monkeypatch.setattr("app.api.v1.routers.tts.synthesize_philosopher_tts", _mock_synthesize)

    response = client.post(
        "/api/v1/tts",
        json={
            "philosopher_id": "socrates",
            "text": "정의는 무엇인가?",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/mpeg")
    assert response.content == b"ID3\x00\x00mock-audio"
    assert captured["philosopher_id"] == Philosopher.socrates
    assert captured["rate_limit_key"] == "user:tts-user"
    app.dependency_overrides.clear()


def test_tts_invalid_payload_returns_error_code() -> None:
    _set_user("tts-invalid")
    response = client.post(
        "/api/v1/tts",
        json={
            "text": "philosopher_id 누락",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "error_code": "TTS_INVALID_REQUEST",
        "message": "Invalid request payload",
    }
    app.dependency_overrides.clear()


def test_tts_text_too_long_returns_domain_error() -> None:
    _set_user("tts-too-long")
    response = client.post(
        "/api/v1/tts",
        json={
            "philosopher_id": "socrates",
            "text": "a" * 2001,
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "error_code": "TTS_TEXT_TOO_LONG",
        "message": "Text length must be less than or equal to 2000",
    }
    app.dependency_overrides.clear()


def test_tts_empty_after_preprocessing_returns_invalid_text() -> None:
    _set_user("tts-empty")
    response = client.post(
        "/api/v1/tts",
        json={
            "philosopher_id": "hannah_arendt",
            "text": "  ### **__~~  ",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "error_code": "TTS_INVALID_TEXT",
        "message": "Text is empty after preprocessing",
    }
    app.dependency_overrides.clear()


def test_tts_rate_limit_error_code(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _set_user("tts-rate-limit")

    def _mock_limited(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise TTSServiceError(
            status_code=429,
            error_code="TTS_RATE_LIMITED",
            message="Too many TTS requests",
        )

    monkeypatch.setattr("app.api.v1.routers.tts.synthesize_philosopher_tts", _mock_limited)
    response = client.post(
        "/api/v1/tts",
        json={
            "philosopher_id": "nietzsche",
            "text": "한계를 시험한다.",
        },
    )

    assert response.status_code == 429
    assert response.json() == {
        "error_code": "TTS_RATE_LIMITED",
        "message": "Too many TTS requests",
    }
    app.dependency_overrides.clear()


def test_tts_retry_after_timeout(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    class _Settings:
        openai_api_key = "test-key"
        tts_openai_model = "gpt-4o-mini-tts"
        tts_timeout_seconds = 8.0
        tts_retry_count = 1

    class _Response:
        def __init__(self, status_code: int, content: bytes) -> None:
            self.status_code = status_code
            self.content = content

    class _Client:
        call_count = 0

        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self) -> "_Client":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
            return None

        def post(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _Client.call_count += 1
            if _Client.call_count == 1:
                raise httpx.TimeoutException("timeout")
            return _Response(200, b"ID3ok")

    monkeypatch.setattr("app.application.services.tts.get_settings", lambda: _Settings())
    monkeypatch.setattr("app.application.services.tts.httpx.Client", _Client)

    audio = _call_tts_provider(
        chunk="테스트 문장",
        profile=VoiceProfile(
            voice_id="sage",
            speed=1.0,
            style="clear",
        ),
    )
    assert audio == b"ID3ok"
    assert _Client.call_count == 2


def test_synthesize_applies_rate_limit(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("app.application.services.tts._call_tts_provider", lambda *args, **kwargs: b"ID3ok")
    limiter = InMemoryRateLimiter(limit_per_minute=1)

    first = synthesize_philosopher_tts(
        philosopher_id=Philosopher.hannah_arendt,
        text="공적 영역에서의 판단",
        rate_limit_key="user:a",
        limiter=limiter,
    )
    assert first == b"ID3ok"

    try:
        synthesize_philosopher_tts(
            philosopher_id=Philosopher.hannah_arendt,
            text="두 번째 요청",
            rate_limit_key="user:a",
            limiter=limiter,
        )
        assert False, "Expected TTSServiceError"
    except TTSServiceError as exc:
        assert exc.status_code == 429
        assert exc.error_code == "TTS_RATE_LIMITED"
