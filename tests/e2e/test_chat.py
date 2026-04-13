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
        lambda philosopher, messages: f"[{philosopher.value}] {messages[-1]['content']}에 대한 응답",
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
