import os
from functools import lru_cache
from typing import Any

import jwt
from fastapi import HTTPException, status
from jwt import InvalidTokenError, PyJWKClient

from app.core.config import get_settings

SUPPORTED_ASYMMETRIC_JWT_ALGORITHMS = ["RS256", "ES256"]
SUPPORTED_SYMMETRIC_JWT_ALGORITHMS = ["HS256"]


def _build_jwks_url(supabase_url: str) -> str:
    return f"{supabase_url}/auth/v1/.well-known/jwks.json"


@lru_cache
def get_jwks_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url)


def verify_supabase_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.supabase_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SUPABASE_URL is not configured",
        )

    jwks_url = _build_jwks_url(settings.supabase_url)
    issuer = f"{settings.supabase_url}/auth/v1"

    try:
        header = jwt.get_unverified_header(token)
        algorithm = header.get("alg")

        if algorithm in SUPPORTED_SYMMETRIC_JWT_ALGORITHMS:
            supabase_jwt_secret = os.getenv("SUPABASE_JWT_SECRET", "").strip()
            if not supabase_jwt_secret:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="SUPABASE_JWT_SECRET is required for HS256 token verification",
                )
            return jwt.decode(
                token,
                supabase_jwt_secret,
                algorithms=[algorithm],
                audience=settings.supabase_jwt_audience,
                issuer=issuer,
            )

        signing_key = get_jwks_client(jwks_url).get_signing_key_from_jwt(token).key
        return jwt.decode(
            token,
            signing_key,
            algorithms=SUPPORTED_ASYMMETRIC_JWT_ALGORITHMS,
            audience=settings.supabase_jwt_audience,
            issuer=issuer,
        )
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        ) from exc
