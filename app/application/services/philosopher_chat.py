from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException, status

from app.core.config import get_settings
from app.infrastructure.db.models import Philosopher

PHILOSOPHER_SYSTEM_PROMPTS: dict[Philosopher, str] = {
    Philosopher.socrates: (
        "You are Socrates. Speak with concise, probing questions and dialectical reasoning. "
        "Do not claim modern knowledge beyond the conversation context."
    ),
    Philosopher.nietzsche: (
        "You are Friedrich Nietzsche. Use aphoristic, provocative phrasing, "
        "value-critique, and genealogy of morals. Avoid modern factual claims unless provided."
    ),
    Philosopher.hannah_arendt: (
        "You are Hannah Arendt. Analyze politics, responsibility, public realm, and judgment "
        "with clarity and conceptual precision."
    ),
}


def _build_input_messages(system_prompt: str, messages: list[dict[str, str]]) -> list[dict[str, str]]:
    payload: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    payload.extend(messages)
    return payload


def generate_philosopher_reply(philosopher: Philosopher, messages: list[dict[str, str]]) -> str:
    settings = get_settings()
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_API_KEY is not configured",
        )

    model = settings.openai_model
    payload = {
        "model": model,
        "input": _build_input_messages(PHILOSOPHER_SYSTEM_PROMPTS[philosopher], messages),
        "temperature": 0.8,
    }

    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=45.0) as client:
            response = client.post(
                "https://api.openai.com/v1/responses",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to generate AI response: {detail}",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to reach AI provider",
        ) from exc

    data: dict[str, Any] = response.json()
    text = data.get("output_text")
    if isinstance(text, str) and text.strip():
        return text.strip()

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="AI provider returned an empty response",
    )
