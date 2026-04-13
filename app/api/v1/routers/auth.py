from typing import Any

from fastapi import APIRouter, Depends

from app.api.v1.dependencies.auth import get_current_user_claims

router = APIRouter(tags=["auth"])


@router.get("/me")
def get_me(claims: dict[str, Any] = Depends(get_current_user_claims)) -> dict[str, Any]:
    return {
        "id": claims.get("sub"),
        "email": claims.get("email"),
        "role": claims.get("role"),
    }
