from pydantic import BaseModel, Field

from app.infrastructure.db.models import Philosopher


class TTSRequest(BaseModel):
    philosopher_id: Philosopher
    text: str = Field(min_length=1, max_length=2000)
