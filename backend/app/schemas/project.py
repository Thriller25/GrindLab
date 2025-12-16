from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel

from app.schemas.flowsheet_version import FlowsheetVersionRead
from app.schemas.user import UserRead
from app.schemas.calc_scenario import CalcScenarioRead
from app.schemas.calc_run import CalcRunListItem
from app.schemas.comment import CommentRead


class ProjectFlowsheetVersionRead(BaseModel):
    id: int
    flowsheet_version_id: int
    flowsheet_name: Optional[str] = None
    flowsheet_version_label: Optional[str] = None
    model_name: Optional[str] = None
    plant_id: Optional[int] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    plant_id: Optional[int] = None


class ProjectCreate(ProjectBase):
    pass


class ProjectRead(ProjectBase):
    id: int
    owner_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectListItem(ProjectRead):
    pass


class ProjectListResponse(BaseModel):
    items: List[ProjectListItem]
    total: int


class ProjectDetail(ProjectRead):
    flowsheet_versions: List[ProjectFlowsheetVersionRead] = []
    flowsheet_summaries: List["ProjectFlowsheetSummary"] = []


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


class CalcRunKpiSummary(BaseModel):
    id: str
    created_at: datetime
    throughput_tph: Optional[float] = None
    product_p80_mm: Optional[float] = None
    specific_energy_kwhpt: Optional[float] = None
    circulating_load_pct: Optional[float] = None
    power_use_pct: Optional[float] = None


class CalcRunKpiDiffSummary(BaseModel):
    throughput_tph_delta: Optional[float] = None
    specific_energy_kwhpt_delta: Optional[float] = None
    p80_mm_delta: Optional[float] = None
    circulating_load_pct_delta: Optional[float] = None
    power_use_pct_delta: Optional[float] = None


class ProjectFlowsheetSummary(BaseModel):
    flowsheet_id: int
    flowsheet_name: str
    flowsheet_version_id: int
    flowsheet_version_label: str
    model_code: str
    plant_name: Optional[str] = None
    has_runs: bool = True
    baseline_run: Optional[CalcRunKpiSummary] = None
    best_project_run: Optional[CalcRunKpiSummary] = None
    diff_vs_baseline: Optional[CalcRunKpiDiffSummary] = None

    model_config = {"from_attributes": True}


# resolve forward references
ProjectDetail.model_rebuild()
