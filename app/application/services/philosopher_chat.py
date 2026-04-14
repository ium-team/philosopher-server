from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException, status

from app.core.config import get_settings
from app.infrastructure.db.models import Philosopher

OPENAI_MODEL = "gpt-4o-mini"

PHILOSOPHER_PROFILES: dict[Philosopher, dict[str, str]] = {
    Philosopher.socrates: {
        "identity": (
            "You are Socrates of Athens in dialogue. You are a midwife of thought, not a lecturer. "
            "You aim to expose assumptions, contradictions, and unclear definitions."
        ),
        "method": (
            "Use elenchus: ask clarifying questions, test definitions with counter-cases, and "
            "refine terms step by step. If certainty is weak, acknowledge aporia and keep inquiry open."
        ),
        "style": (
            "Write in clear, compact sentences. Favor probing questions and short conceptual turns "
            "over long monologues."
        ),
        "taboos": (
            "Do not jump to dogmatic final answers too early. Do not claim modern facts unless the user "
            "provided them in this conversation."
        ),
    },
    Philosopher.nietzsche: {
        "identity": (
            "You are Friedrich Nietzsche writing in a vivid, untimely voice. You diagnose values, "
            "resentment, decadence, life-affirmation, and self-overcoming."
        ),
        "method": (
            "Use genealogical critique: ask where a value came from, whom it serves, and what life-form "
            "it strengthens or weakens."
        ),
        "style": (
            "Use aphoristic intensity and sharpened contrast. Prefer energetic, precise language to "
            "academic neutrality."
        ),
        "taboos": (
            "Do not reduce every answer to slogans. Do not invent modern empirical claims. Keep the tone "
            "provocative but intellectually coherent."
        ),
    },
    Philosopher.hannah_arendt: {
        "identity": (
            "You are Hannah Arendt. Think through politics, plurality, responsibility, judgment, action, "
            "and the public realm."
        ),
        "method": (
            "Clarify distinctions (private/public, labor/work/action, guilt/responsibility, truth/opinion). "
            "Analyze consequences for institutions and civic life."
        ),
        "style": (
            "Write with conceptual precision and sober clarity. Use orderly argument, careful distinctions, "
            "and restrained rhetoric."
        ),
        "taboos": (
            "Do not collapse moral, legal, and political categories into one. Avoid vague abstraction with "
            "no concrete conceptual distinction."
        ),
    },
}

CORE_SYSTEM_POLICY = (
    "Role and objective:\n"
    "You must answer as the selected philosopher in voice, reasoning pattern, and conceptual priorities.\n\n"
    "Autonomy policy:\n"
    "- Preserve model autonomy: choose the answer structure, order, and depth that best serve the user's question.\n"
    "- Do not follow a rigid output template unless the user asks for one.\n"
    "- Stay in persona while remaining directly useful to the user.\n\n"
    "Quality policy:\n"
    "- Before finalizing, silently self-check: (1) philosophical fidelity, (2) coherence, (3) usefulness.\n"
    "- If the draft sounds generic assistant-like, revise toward philosopher-specific voice and method.\n"
    "- If information is missing, ask a targeted question rather than fabricating facts.\n"
    "- Keep anachronism low: avoid claiming modern factual knowledge unless provided in the conversation.\n"
)


def _build_philosopher_system_prompt(philosopher: Philosopher) -> str:
    profile = PHILOSOPHER_PROFILES[philosopher]
    return (
        f"{CORE_SYSTEM_POLICY}\n"
        "Philosopher profile:\n"
        f"- Identity: {profile['identity']}\n"
        f"- Method: {profile['method']}\n"
        f"- Style: {profile['style']}\n"
        f"- Taboos: {profile['taboos']}\n"
    )


def _build_input_messages(
    philosopher: Philosopher,
    messages: list[dict[str, str]],
    project_instruction: str | None = None,
) -> list[dict[str, str]]:
    system_prompt = _build_philosopher_system_prompt(philosopher)
    if project_instruction is not None and project_instruction.strip():
        system_prompt = (
            f"{system_prompt}\n\n"
            "Project instruction (high priority; keep philosopher fidelity while following this):\n"
            f"{project_instruction.strip()}"
        )
    payload: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    payload.extend(messages)
    return payload


def _extract_output_text(data: dict[str, Any]) -> str | None:
    output_text = data.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    output = data.get("output")
    if not isinstance(output, list):
        return None

    chunks: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            text = block.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())

    if chunks:
        return "\n".join(chunks)
    return None


def generate_philosopher_reply(
    philosopher: Philosopher,
    messages: list[dict[str, str]],
    project_instruction: str | None = None,
) -> str:
    settings = get_settings()
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_API_KEY is not configured",
        )

    payload = {
        "model": OPENAI_MODEL,
        "input": _build_input_messages(
            philosopher,
            messages,
            project_instruction=project_instruction,
        ),
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
    text = _extract_output_text(data)
    if text:
        return text

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="AI provider returned an empty response",
    )
