from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.schemas.calc_io import CalcInput


class CalcScenarioBase(BaseModel):
    name: str
    description: Optional[str] = None
    default_input_json: CalcInput
    is_baseline: bool = False


class CalcScenarioCreate(CalcScenarioBase):
    flowsheet_version_id: UUID


class CalcScenarioUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    default_input_json: Optional[CalcInput] = None
    is_baseline: Optional[bool] = None


class CalcScenarioRead(CalcScenarioBase):
    id: UUID
    flowsheet_version_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CalcScenarioListItem(BaseModel):
    id: UUID
    name: str
    flowsheet_version_id: UUID
    is_baseline: bool = False

    model_config = {"from_attributes": True}


class CalcScenarioListResponse(BaseModel):
    items: list[CalcScenarioListItem]
    total: int
