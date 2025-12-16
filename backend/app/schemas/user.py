from datetime import datetime
from typing import Dict, Optional
from uuid import UUID

from pydantic import BaseModel


class UserBase(BaseModel):
    email: str
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str


class UserRead(UserBase):
    id: UUID
    is_active: bool
    is_superuser: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserLogin(BaseModel):
    email: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserActivitySummary(BaseModel):
    user: UserRead
    scenarios_total: int
    calc_runs_total: int
    calc_runs_by_status: Dict[str, int]
    comments_total: int
    last_activity_at: Optional[datetime] = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
