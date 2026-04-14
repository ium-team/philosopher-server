from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.api.v1.dependencies.auth import get_current_user_claims
from app.api.v1.schemas.chat import (
    ConversationCreateRequest,
    ConversationProjectMoveRequest,
    ConversationResponse,
    MessageExchangeResponse,
    MessageResponse,
    MessageSendRequest,
    ProjectCreateRequest,
    ProjectResponse,
    ProjectSettingsUpdateRequest,
)
from app.application.services.philosopher_chat import generate_philosopher_reply
from app.infrastructure.db.models import Conversation, Message, MessageRole, Project
from app.infrastructure.db.session import get_db_session

router = APIRouter(prefix="/chat", tags=["chat"])


def _current_user_id(claims: dict[str, Any]) -> str:
    user_id = claims.get("sub")
    if not isinstance(user_id, str) or not user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user claims",
        )
    return user_id


def _fetch_one_or_404(db: Session, statement: Select[Any], detail: str) -> Any:
    instance = db.execute(statement).scalar_one_or_none()
    if instance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return instance


def _get_or_create_default_project(db: Session, user_id: str) -> Project:
    default_project = db.execute(
        select(Project).where(Project.user_id == user_id, Project.is_default.is_(True)),
    ).scalar_one_or_none()
    if default_project is not None:
        return default_project

    default_project = Project(
        user_id=user_id,
        name="DEFAULT",
        is_default=True,
    )
    db.add(default_project)
    db.flush()
    return default_project


def _fetch_visible_project_or_404(db: Session, project_id: str, user_id: str) -> Project:
    return _fetch_one_or_404(
        db,
        select(Project).where(
            Project.id == project_id,
            Project.user_id == user_id,
            Project.is_default.is_(False),
        ),
        "Project not found",
    )


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    request: ProjectCreateRequest,
    claims: dict[str, Any] = Depends(get_current_user_claims),
    db: Session = Depends(get_db_session),
) -> Project:
    user_id = _current_user_id(claims)
    project = Project(
        user_id=user_id,
        name=request.name.strip(),
        description=request.description,
        instruction=request.instruction.strip() if request.instruction is not None else None,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/projects", response_model=list[ProjectResponse])
def list_projects(
    claims: dict[str, Any] = Depends(get_current_user_claims),
    db: Session = Depends(get_db_session),
) -> list[Project]:
    user_id = _current_user_id(claims)
    statement = (
        select(Project)
        .where(Project.user_id == user_id, Project.is_default.is_(False))
        .order_by(Project.updated_at.desc(), Project.created_at.desc())
    )
    return list(db.execute(statement).scalars().all())


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_default_conversation(
    request: ConversationCreateRequest,
    claims: dict[str, Any] = Depends(get_current_user_claims),
    db: Session = Depends(get_db_session),
) -> Conversation:
    user_id = _current_user_id(claims)
    default_project = _get_or_create_default_project(db, user_id)
    conversation = Conversation(
        user_id=user_id,
        project_id=default_project.id,
        philosopher=request.philosopher,
        title=request.title,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.post(
    "/projects/{project_id}/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    project_id: str,
    request: ConversationCreateRequest,
    claims: dict[str, Any] = Depends(get_current_user_claims),
    db: Session = Depends(get_db_session),
) -> Conversation:
    user_id = _current_user_id(claims)
    _fetch_visible_project_or_404(db, project_id, user_id)

    conversation = Conversation(
        user_id=user_id,
        project_id=project_id,
        philosopher=request.philosopher,
        title=request.title,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("/projects/{project_id}/conversations", response_model=list[ConversationResponse])
def list_conversations(
    project_id: str,
    claims: dict[str, Any] = Depends(get_current_user_claims),
    db: Session = Depends(get_db_session),
) -> list[Conversation]:
    user_id = _current_user_id(claims)
    _fetch_visible_project_or_404(db, project_id, user_id)
    statement = (
        select(Conversation)
        .where(Conversation.project_id == project_id, Conversation.user_id == user_id)
        .order_by(Conversation.created_at.desc())
    )
    return list(db.execute(statement).scalars().all())


@router.patch("/projects/{project_id}/settings", response_model=ProjectResponse)
def update_project_settings(
    project_id: str,
    request: ProjectSettingsUpdateRequest,
    claims: dict[str, Any] = Depends(get_current_user_claims),
    db: Session = Depends(get_db_session),
) -> Project:
    user_id = _current_user_id(claims)
    project = _fetch_visible_project_or_404(db, project_id, user_id)
    if request.name is not None:
        project.name = request.name.strip()
    if request.instruction is not None:
        project.instruction = request.instruction.strip()
    db.commit()
    db.refresh(project)
    return project


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: str,
    claims: dict[str, Any] = Depends(get_current_user_claims),
    db: Session = Depends(get_db_session),
) -> Response:
    user_id = _current_user_id(claims)
    project = _fetch_visible_project_or_404(db, project_id, user_id)
    db.delete(project)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/conversations/{conversation_id}/project", response_model=ConversationResponse)
def move_conversation_project(
    conversation_id: str,
    request: ConversationProjectMoveRequest,
    claims: dict[str, Any] = Depends(get_current_user_claims),
    db: Session = Depends(get_db_session),
) -> Conversation:
    user_id = _current_user_id(claims)
    conversation = _fetch_one_or_404(
        db,
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id),
        "Conversation not found",
    )
    project = (
        _get_or_create_default_project(db, user_id)
        if request.project_id is None
        else _fetch_visible_project_or_404(db, request.project_id, user_id)
    )
    conversation.project_id = project.id
    db.commit()
    db.refresh(conversation)
    return conversation


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: str,
    claims: dict[str, Any] = Depends(get_current_user_claims),
    db: Session = Depends(get_db_session),
) -> Response:
    user_id = _current_user_id(claims)
    conversation = _fetch_one_or_404(
        db,
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id),
        "Conversation not found",
    )
    db.delete(conversation)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
def list_messages(
    conversation_id: str,
    claims: dict[str, Any] = Depends(get_current_user_claims),
    db: Session = Depends(get_db_session),
) -> list[Message]:
    user_id = _current_user_id(claims)
    _fetch_one_or_404(
        db,
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id),
        "Conversation not found",
    )

    statement = select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.asc())
    return list(db.execute(statement).scalars().all())


@router.post("/conversations/{conversation_id}/messages", response_model=MessageExchangeResponse)
def send_message(
    conversation_id: str,
    request: MessageSendRequest,
    claims: dict[str, Any] = Depends(get_current_user_claims),
    db: Session = Depends(get_db_session),
) -> MessageExchangeResponse:
    user_id = _current_user_id(claims)
    conversation = _fetch_one_or_404(
        db,
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id),
        "Conversation not found",
    )
    project = _fetch_one_or_404(
        db,
        select(Project).where(Project.id == conversation.project_id, Project.user_id == user_id),
        "Project not found",
    )

    user_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.user,
        content=request.content.strip(),
    )
    db.add(user_message)
    db.flush()

    history_statement = select(Message).where(Message.conversation_id == conversation.id).order_by(Message.created_at.asc())
    history = list(db.execute(history_statement).scalars().all())
    ai_input = [{"role": msg.role.value, "content": msg.content} for msg in history]
    assistant_text = generate_philosopher_reply(
        conversation.philosopher,
        ai_input,
        project_instruction=project.instruction,
    )

    assistant_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.assistant,
        content=assistant_text,
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(user_message)
    db.refresh(assistant_message)

    return MessageExchangeResponse(
        user_message=MessageResponse.model_validate(user_message),
        assistant_message=MessageResponse.model_validate(assistant_message),
    )
