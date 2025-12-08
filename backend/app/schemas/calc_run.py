from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.schemas.calc_io import CalcInput, CalcResultSummary


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
    result_json: Optional[CalcResultSummary] = None
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
    result_json: Optional[CalcResultSummary] = None

    model_config = {"from_attributes": True}


class CalcRunListResponse(BaseModel):
    items: list[CalcRunListItem]
    total: int
