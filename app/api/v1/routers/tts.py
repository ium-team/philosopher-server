from typing import Any

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError

from app.api.v1.dependencies.auth import get_current_user_claims
from app.api.v1.schemas.tts import TTSRequest
from app.application.services.tts import InMemoryRateLimiter, TTSServiceError, synthesize_philosopher_tts
from app.core.config import get_settings

router = APIRouter(tags=["tts"])
_tts_rate_limiter = InMemoryRateLimiter(limit_per_minute=get_settings().tts_rate_limit_per_minute)


def _current_user_id(claims: dict[str, Any]) -> str:
    user_id = claims.get("sub")
    if not isinstance(user_id, str) or not user_id.strip():
        raise TTSServiceError(
            status_code=401,
            error_code="TTS_UNAUTHORIZED",
            message="Invalid user claims",
        )
    return user_id


def _error_response(error: TTSServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={
            "error_code": error.error_code,
            "message": error.message,
        },
    )


@router.post("/tts")
def generate_tts(
    payload: dict[str, Any] = Body(...),
    claims: dict[str, Any] = Depends(get_current_user_claims),
) -> Response | JSONResponse:
    try:
        request = TTSRequest.model_validate(payload)
    except ValidationError:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "TTS_INVALID_REQUEST",
                "message": "Invalid request payload",
            },
        )

    try:
        user_id = _current_user_id(claims)
        audio = synthesize_philosopher_tts(
            philosopher_id=request.philosopher_id,
            text=request.text,
            rate_limit_key=f"user:{user_id}",
            limiter=_tts_rate_limiter,
        )
    except TTSServiceError as error:
        return _error_response(error)

    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-store"},
    )
