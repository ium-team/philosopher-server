from __future__ import annotations

import re
import threading
from collections import deque
from dataclasses import dataclass
from time import monotonic

import httpx

from app.core.config import get_settings
from app.infrastructure.db.models import Philosopher


@dataclass(frozen=True)
class VoiceProfile:
    voice_id: str
    speed: float
    style: str


VOICE_PROFILES: dict[Philosopher, VoiceProfile] = {
    Philosopher.socrates: VoiceProfile(
        voice_id="onyx",
        speed=0.93,
        style="Warm low male voice, calm and probing, deliberate pauses for reflective questioning.",
    ),
    Philosopher.nietzsche: VoiceProfile(
        voice_id="echo",
        speed=1.08,
        style="Bright male voice with sharp contrast, energetic emphasis, and assertive cadence.",
    ),
    Philosopher.hannah_arendt: VoiceProfile(
        voice_id="nova",
        speed=0.96,
        style="Clear female voice, composed and analytical, precise diction with steady pacing.",
    ),
    Philosopher.plato: VoiceProfile(
        voice_id="onyx",
        speed=0.93,
        style="Composed male voice, reflective and dialogic, deliberate cadence that guides ideas upward.",
    ),
    Philosopher.aristotle: VoiceProfile(
        voice_id="echo",
        speed=0.98,
        style="Clear male voice with measured pacing, structured emphasis, and practical precision.",
    ),
    Philosopher.rene_descartes: VoiceProfile(
        voice_id="alloy",
        speed=0.97,
        style="Focused male voice, calm and methodical, with crisp articulation for stepwise reasoning.",
    ),
    Philosopher.immanuel_kant: VoiceProfile(
        voice_id="fable",
        speed=0.92,
        style="Steady male voice, formal and disciplined, emphasizing conceptual distinctions.",
    ),
    Philosopher.confucius: VoiceProfile(
        voice_id="nova",
        speed=0.96,
        style="Warm balanced voice, calm and instructive, with respectful tone and practical cadence.",
    ),
    Philosopher.simone_de_beauvoir: VoiceProfile(
        voice_id="shimmer",
        speed=1.0,
        style="Thoughtful female voice, clear and firm, combining critical nuance with humane warmth.",
    ),
}


class TTSServiceError(Exception):
    def __init__(self, status_code: int, error_code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message


class InMemoryRateLimiter:
    def __init__(self, limit_per_minute: int) -> None:
        self.limit_per_minute = limit_per_minute
        self.window_seconds = 60.0
        self._buckets: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            bucket = self._buckets.setdefault(key, deque())
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit_per_minute:
                return False
            bucket.append(now)
            return True


def _strip_markdown_and_symbols(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"```[\s\S]*?```", " ", cleaned)
    cleaned = re.sub(r"`([^`]*)`", r"\1", cleaned)
    cleaned = re.sub(r"!\[[^\]]*]\([^)]*\)", " ", cleaned)
    cleaned = re.sub(r"\[([^\]]+)]\([^)]*\)", r"\1", cleaned)
    cleaned = re.sub(r"[*_~#>|]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _split_text(text: str, max_chunk_chars: int) -> list[str]:
    if len(text) <= max_chunk_chars:
        return [text]

    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= max_chunk_chars:
            chunks.append(remaining)
            break

        split_at = max(remaining.rfind(". ", 0, max_chunk_chars), remaining.rfind("? ", 0, max_chunk_chars))
        split_at = max(split_at, remaining.rfind("! ", 0, max_chunk_chars))
        split_at = max(split_at, remaining.rfind(" ", 0, max_chunk_chars))
        if split_at <= 0:
            split_at = max_chunk_chars

        chunk = remaining[:split_at].strip()
        if not chunk:
            chunk = remaining[:max_chunk_chars].strip()
            split_at = max_chunk_chars
        chunks.append(chunk)
        remaining = remaining[split_at:].strip()
    return chunks


def _call_tts_provider(chunk: str, profile: VoiceProfile) -> bytes:
    settings = get_settings()
    if not settings.openai_api_key:
        raise TTSServiceError(
            status_code=503,
            error_code="TTS_NOT_CONFIGURED",
            message="OPENAI_API_KEY is not configured",
        )

    payload = {
        "model": settings.tts_openai_model,
        "voice": profile.voice_id,
        "input": chunk,
        "response_format": "mp3",
        "speed": profile.speed,
        "instructions": profile.style,
    }
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }

    attempts = settings.tts_retry_count + 1
    last_exc: Exception | None = None
    for _ in range(attempts):
        try:
            with httpx.Client(timeout=settings.tts_timeout_seconds) as client:
                response = client.post(
                    "https://api.openai.com/v1/audio/speech",
                    json=payload,
                    headers=headers,
                )
            if response.status_code == 408 or response.status_code == 504:
                raise TTSServiceError(
                    status_code=504,
                    error_code="TTS_PROVIDER_TIMEOUT",
                    message="TTS provider timed out",
                )
            if 500 <= response.status_code <= 599:
                last_exc = TTSServiceError(
                    status_code=502,
                    error_code="TTS_PROVIDER_UNAVAILABLE",
                    message="TTS provider temporary failure",
                )
                continue
            if response.status_code >= 400:
                raise TTSServiceError(
                    status_code=502,
                    error_code="TTS_PROVIDER_ERROR",
                    message="TTS provider rejected request",
                )
            return response.content
        except httpx.TimeoutException as exc:
            last_exc = exc
            continue
        except httpx.HTTPError as exc:
            last_exc = exc
            continue
        except TTSServiceError:
            raise

    if isinstance(last_exc, TTSServiceError):
        raise last_exc
    if isinstance(last_exc, httpx.TimeoutException):
        raise TTSServiceError(
            status_code=504,
            error_code="TTS_PROVIDER_TIMEOUT",
            message="TTS provider timed out",
        ) from last_exc
    if isinstance(last_exc, httpx.HTTPError):
        raise TTSServiceError(
            status_code=502,
            error_code="TTS_PROVIDER_UNAVAILABLE",
            message="Failed to reach TTS provider",
        ) from last_exc

    raise TTSServiceError(
        status_code=502,
        error_code="TTS_PROVIDER_UNAVAILABLE",
        message="Unknown TTS provider failure",
    )


def synthesize_philosopher_tts(
    philosopher_id: Philosopher,
    text: str,
    rate_limit_key: str,
    limiter: InMemoryRateLimiter,
) -> bytes:
    settings = get_settings()
    normalized_text = _strip_markdown_and_symbols(text)
    if not normalized_text:
        raise TTSServiceError(
            status_code=400,
            error_code="TTS_INVALID_TEXT",
            message="Text is empty after preprocessing",
        )
    if len(normalized_text) > settings.tts_max_chars:
        raise TTSServiceError(
            status_code=400,
            error_code="TTS_TEXT_TOO_LONG",
            message=f"Text length must be less than or equal to {settings.tts_max_chars}",
        )

    if not limiter.allow(rate_limit_key):
        raise TTSServiceError(
            status_code=429,
            error_code="TTS_RATE_LIMITED",
            message="Too many TTS requests",
        )

    profile = VOICE_PROFILES[philosopher_id]
    chunks = _split_text(normalized_text, settings.tts_chunk_chars)

    audio_parts = [_call_tts_provider(chunk, profile) for chunk in chunks if chunk]
    if not audio_parts:
        raise TTSServiceError(
            status_code=502,
            error_code="TTS_EMPTY_AUDIO",
            message="TTS provider returned empty audio",
        )
    return b"".join(audio_parts)
