from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.api.v1.dependencies.auth import get_current_user_claims
from app.infrastructure.db.models import Conversation, Message, Project
from app.infrastructure.db.session import engine, init_db
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_chat_tables() -> Generator[None, None, None]:
    init_db()
    with Session(engine) as session:
        session.execute(delete(Message))
        session.execute(delete(Conversation))
        session.execute(delete(Project))
        session.commit()
    yield


def _set_user(user_id: str) -> None:
    app.dependency_overrides[get_current_user_claims] = lambda: {
        "sub": user_id,
        "email": f"{user_id}@example.com",
        "role": "authenticated",
    }


def test_project_conversation_and_message_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_user("user-1")
    monkeypatch.setattr(
        "app.api.v1.routers.chat.generate_philosopher_reply",
        lambda philosopher, messages, project_instruction=None: (
            f"[{philosopher.value}] {messages[-1]['content']}에 대한 응답 / {project_instruction}"
        ),
    )

    create_project = client.post(
        "/api/v1/chat/projects",
        json={"name": "윤리학 프로젝트", "description": "도덕 철학 토론"},
    )
    assert create_project.status_code == 201
    project_id = create_project.json()["id"]

    create_conversation = client.post(
        f"/api/v1/chat/projects/{project_id}/conversations",
        json={"philosopher": "socrates", "title": "정의란 무엇인가"},
    )
    assert create_conversation.status_code == 201
    conversation_id = create_conversation.json()["id"]

    send_message = client.post(
        f"/api/v1/chat/conversations/{conversation_id}/messages",
        json={"content": "정의는 배울 수 있는가?"},
    )
    assert send_message.status_code == 200
    payload = send_message.json()
    assert payload["user_message"]["role"] == "user"
    assert payload["assistant_message"]["role"] == "assistant"
    assert "socrates" in payload["assistant_message"]["content"]

    list_messages = client.get(f"/api/v1/chat/conversations/{conversation_id}/messages")
    assert list_messages.status_code == 200
    messages = list_messages.json()
    assert len(messages) == 2
    assert [msg["role"] for msg in messages] == ["user", "assistant"]

    app.dependency_overrides.clear()


def test_user_cannot_access_other_users_project() -> None:
    _set_user("owner")
    project_res = client.post("/api/v1/chat/projects", json={"name": "개인 프로젝트"})
    assert project_res.status_code == 201
    project_id = project_res.json()["id"]

    _set_user("other")
    response = client.get(f"/api/v1/chat/projects/{project_id}/conversations")
    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"

    app.dependency_overrides.clear()


def test_create_default_conversation_without_visible_default_project() -> None:
    _set_user("default-owner")

    create_default_conversation = client.post(
        "/api/v1/chat/conversations",
        json={"philosopher": "hannah_arendt", "title": "기본 대화"},
    )
    assert create_default_conversation.status_code == 201
    payload = create_default_conversation.json()
    assert payload["title"] == "기본 대화"
    assert payload["project_id"]

    list_projects = client.get("/api/v1/chat/projects")
    assert list_projects.status_code == 200
    assert list_projects.json() == []

    app.dependency_overrides.clear()


def test_pin_move_and_project_settings_instruction(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_user("user-settings")
    captured: dict[str, str | None] = {"instruction": None}

    def _mock_ai_reply(philosopher, messages, project_instruction=None):  # type: ignore[no-untyped-def]
        captured["instruction"] = project_instruction
        return f"[{philosopher.value}] ok"

    monkeypatch.setattr("app.api.v1.routers.chat.generate_philosopher_reply", _mock_ai_reply)

    first_project = client.post("/api/v1/chat/projects", json={"name": "A 프로젝트"})
    second_project = client.post("/api/v1/chat/projects", json={"name": "B 프로젝트"})
    assert first_project.status_code == 201
    assert second_project.status_code == 201
    first_project_id = first_project.json()["id"]
    second_project_id = second_project.json()["id"]

    pin_res = client.patch(f"/api/v1/chat/projects/{second_project_id}/pin", json={"is_pinned": True})
    assert pin_res.status_code == 200
    assert pin_res.json()["is_pinned"] is True

    project_list_res = client.get("/api/v1/chat/projects")
    assert project_list_res.status_code == 200
    project_list = project_list_res.json()
    assert [project["id"] for project in project_list] == [second_project_id, first_project_id]

    update_settings = client.patch(
        f"/api/v1/chat/projects/{first_project_id}/settings",
        json={"name": "A 프로젝트 수정", "instruction": "항상 3줄로 답해줘"},
    )
    assert update_settings.status_code == 200
    assert update_settings.json()["name"] == "A 프로젝트 수정"
    assert update_settings.json()["instruction"] == "항상 3줄로 답해줘"

    create_conversation = client.post(
        f"/api/v1/chat/projects/{first_project_id}/conversations",
        json={"philosopher": "socrates"},
    )
    assert create_conversation.status_code == 201
    conversation_id = create_conversation.json()["id"]

    move_res = client.patch(
        f"/api/v1/chat/conversations/{conversation_id}/project",
        json={"project_id": second_project_id},
    )
    assert move_res.status_code == 200
    assert move_res.json()["project_id"] == second_project_id

    move_back_res = client.patch(
        f"/api/v1/chat/conversations/{conversation_id}/project",
        json={"project_id": first_project_id},
    )
    assert move_back_res.status_code == 200
    assert move_back_res.json()["project_id"] == first_project_id

    move_to_main_res = client.patch(
        f"/api/v1/chat/conversations/{conversation_id}/project",
        json={"project_id": None},
    )
    assert move_to_main_res.status_code == 200
    assert move_to_main_res.json()["project_id"]
    assert move_to_main_res.json()["project_id"] not in {first_project_id, second_project_id}

    send_message = client.post(
        f"/api/v1/chat/conversations/{conversation_id}/messages",
        json={"content": "지침 적용 확인"},
    )
    assert send_message.status_code == 200
    assert captured["instruction"] == "항상 3줄로 답해줘"

    app.dependency_overrides.clear()
