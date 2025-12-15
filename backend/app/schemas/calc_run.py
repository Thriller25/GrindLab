from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.schemas.calc_io import CalcInput, CalcResultSummary
from app.schemas.calc_result import CalcResult


class CalcRunCreate(BaseModel):
    flowsheet_version_id: UUID
    scenario_id: Optional[UUID] = None
    scenario_name: Optional[str] = None
    comment: Optional[str] = None
    input_json: Optional[CalcInput] = None


class CalcRunRead(BaseModel):
    id: UUID
    flowsheet_version_id: UUID
    scenario_id: Optional[UUID] = None
    scenario_name: Optional[str] = None
    comment: Optional[str] = None
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error_message: Optional[str] = None
    input_json: Optional[CalcInput] = None
    result_json: Optional[CalcResult] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CalcRunListItem(BaseModel):
    id: UUID
    flowsheet_version_id: UUID
    scenario_id: Optional[UUID] = None
    scenario_name: Optional[str] = None
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    comment: Optional[str] = None
    error_message: Optional[str] = None
    input_json: Optional[CalcInput] = None
    result_json: Optional[CalcResult] = None

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
