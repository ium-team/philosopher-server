from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.infrastructure.db.models import MessageRole, Philosopher


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    instruction: str | None = Field(default=None, max_length=4000)


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    instruction: str | None
    is_pinned: bool
    created_at: datetime
    updated_at: datetime | None


class ConversationCreateRequest(BaseModel):
    philosopher: Philosopher
    title: str | None = Field(default=None, max_length=200)


class ProjectPinUpdateRequest(BaseModel):
    is_pinned: bool


class ProjectSettingsUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    instruction: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> "ProjectSettingsUpdateRequest":
        if self.name is None and self.instruction is None:
            raise ValueError("At least one of name or instruction is required")
        return self


class ConversationProjectMoveRequest(BaseModel):
    project_id: str | None = Field(default=None, min_length=1, max_length=36)


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    philosopher: Philosopher
    title: str | None
    created_at: datetime


class MessageSendRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: MessageRole
    content: str
    created_at: datetime


class MessageExchangeResponse(BaseModel):
    user_message: MessageResponse
    assistant_message: MessageResponse
