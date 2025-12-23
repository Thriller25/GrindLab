import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, computed_field, field_validator, model_validator


def _validate_text(value: str) -> str:
    trimmed = value.strip()
    if len(trimmed) < 1:
        raise ValueError("text must not be empty")
    if len(trimmed) > 2000:
        raise ValueError("text must be at most 2000 characters long")
    return trimmed


class CommentBase(BaseModel):
    scenario_id: Optional[uuid.UUID] = None
    calc_run_id: Optional[uuid.UUID] = None
    author: Optional[str] = None
    text: str

    @field_validator("text")
    @classmethod
    def _normalize_text(cls, value: str) -> str:
        return _validate_text(value)


class CommentCreate(CommentBase):
    @model_validator(mode="after")
    def _ensure_single_target(self) -> "CommentCreate":
        has_scenario = self.scenario_id is not None
        has_run = self.calc_run_id is not None
        if has_scenario == has_run:
            raise ValueError("Either scenario_id or calc_run_id must be provided (but not both)")
        return self


class CommentRead(CommentBase):
    id: uuid.UUID
    project_id: int
    created_at: datetime

    @computed_field
    @property
    def target_type(self) -> Literal["scenario", "calc_run"]:
        return "scenario" if self.scenario_id is not None else "calc_run"

    model_config = {"from_attributes": True}


class CommentListResponse(BaseModel):
    items: list[CommentRead]
    total: int


class UserCommentCreate(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def _normalize_text(cls, value: str) -> str:
        return _validate_text(value)
