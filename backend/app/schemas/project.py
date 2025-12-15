import uuid
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel

from app.schemas.flowsheet_version import FlowsheetVersionRead
from app.schemas.user import UserRead
from app.schemas.calc_scenario import CalcScenarioRead
from app.schemas.calc_run import CalcRunListItem
from app.schemas.comment import CommentRead

class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectCreate(ProjectBase):
    pass


class ProjectRead(ProjectBase):
    id: uuid.UUID
    owner_user_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectListItem(ProjectRead):
    pass


class ProjectListResponse(BaseModel):
    items: List[ProjectListItem]
    total: int


class ProjectDetail(ProjectRead):
    flowsheet_versions: List[FlowsheetVersionRead] = []


class ProjectSummary(BaseModel):
    project: ProjectRead
    flowsheet_versions_total: int
    scenarios_total: int
    calc_runs_total: int
    calc_runs_by_status: Dict[str, int]
    comments_total: int
    last_activity_at: Optional[datetime] = None


class ProjectMemberAddRequest(BaseModel):
    email: str
    role: str = "editor"


class ProjectMemberRead(BaseModel):
    user: UserRead
    role: str
    added_at: datetime


class ProjectDashboardResponse(BaseModel):
    project: ProjectRead
    summary: ProjectSummary
    flowsheet_versions: List[FlowsheetVersionRead]
    scenarios: List[CalcScenarioRead]
    recent_calc_runs: List[CalcRunListItem]
    recent_comments: List[CommentRead]
