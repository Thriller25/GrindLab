from datetime import datetime
from typing import Dict, Optional, List, TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.schemas.project import ProjectRead
    from app.schemas.calc_run import CalcRunListItem
    from app.schemas.comment import CommentRead
    from app.schemas.calc_scenario import CalcScenarioRead


class UserBase(BaseModel):
    email: str
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str


class UserRead(UserBase):
    id: int
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


class UserFavoritesGrouped(BaseModel):
    projects: List["ProjectRead"] = Field(default_factory=list)
    scenarios: List["CalcScenarioRead"] = Field(default_factory=list)
    calc_runs: List["CalcRunListItem"] = Field(default_factory=list)


class UserDashboardResponse(BaseModel):
    user: UserRead
    summary: UserActivitySummary
    projects: List["ProjectRead"]
    member_projects: List["ProjectRead"]
    recent_calc_runs: List["CalcRunListItem"]
    recent_comments: List["CommentRead"]
    favorites: "UserFavoritesGrouped" = Field(default_factory=lambda: UserFavoritesGrouped())
