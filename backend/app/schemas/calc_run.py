from datetime import datetime
from typing import Optional
from uuid import UUID

from app.schemas.calc_io import CalcInput, CalcResultSummary
from pydantic import BaseModel


class CalcRunCreate(BaseModel):
    flowsheet_version_id: UUID
    scenario_id: Optional[UUID] = None
    scenario_name: Optional[str] = None
    project_id: Optional[int] = None
    comment: Optional[str] = None
    input_json: Optional[CalcInput] = None
    started_by_user_id: Optional[UUID] = None


class CalcRunRead(BaseModel):
    id: UUID
    flowsheet_version_id: UUID
    scenario_id: Optional[UUID] = None
    scenario_name: Optional[str] = None
    project_id: Optional[int] = None
    comment: Optional[str] = None
    started_by_user_id: Optional[UUID] = None
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error_message: Optional[str] = None
    input_json: Optional[CalcInput] = None
    result_json: Optional[CalcResultSummary] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CalcRunListItem(BaseModel):
    id: UUID
    flowsheet_version_id: UUID
    scenario_id: Optional[UUID] = None
    scenario_name: Optional[str] = None
    project_id: Optional[int] = None
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    comment: Optional[str] = None
    error_message: Optional[str] = None
    started_by_user_id: Optional[UUID] = None
    input_json: Optional[CalcInput] = None
    result_json: Optional[CalcResultSummary] = None

    model_config = {"from_attributes": True}


class CalcRunListResponse(BaseModel):
    items: list[CalcRunListItem]
    total: int


class CalcRunComparisonItem(BaseModel):
    id: UUID
    scenario_id: Optional[UUID] = None
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    input: CalcInput
    result: Optional[CalcResultSummary] = None


class CalcRunCompareResponse(BaseModel):
    items: list[CalcRunComparisonItem]
    total: int


class CalcRunDelta(BaseModel):
    throughput_delta_abs: Optional[float] = None
    throughput_delta_pct: Optional[float] = None
    specific_energy_delta_abs: Optional[float] = None
    specific_energy_delta_pct: Optional[float] = None
    p80_out_delta_abs: Optional[float] = None
    p80_out_delta_pct: Optional[float] = None


class CalcRunCompareWithBaselineItem(BaseModel):
    run: CalcRunComparisonItem
    deltas: CalcRunDelta


class CalcRunCompareWithBaselineResponse(BaseModel):
    baseline: CalcRunComparisonItem
    items: list[CalcRunCompareWithBaselineItem]
    total: int


class BatchRunRequest(BaseModel):
    """Request to run multiple scenarios"""

    flowsheet_version_id: UUID
    scenario_ids: list[UUID]
    project_id: Optional[int] = None
    comment: Optional[str] = None


class BatchRunResponse(BaseModel):
    """Response containing multiple created runs"""

    runs: list[CalcRunRead]
    total: int
