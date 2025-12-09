import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


class CommentBase(BaseModel):
    author: Optional[str] = None
    text: str


class CommentCreate(CommentBase):
    entity_type: Literal["calc_run", "scenario"]
    entity_id: uuid.UUID


class CommentRead(CommentBase):
    id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CommentListResponse(BaseModel):
    items: list[CommentRead]
    total: int
