import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.schemas.calc_run import CalcRunCompareResponse


class CalcComparisonBase(BaseModel):
    name: str
    description: Optional[str] = None
    run_ids: list[uuid.UUID]


class CalcComparisonCreate(CalcComparisonBase):
    flowsheet_version_id: uuid.UUID


class CalcComparisonRead(CalcComparisonBase):
    id: uuid.UUID
    flowsheet_version_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CalcComparisonListItem(BaseModel):
    id: uuid.UUID
    flowsheet_version_id: uuid.UUID
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CalcComparisonListResponse(BaseModel):
    items: list[CalcComparisonListItem]
    total: int


class CalcComparisonDetailResponse(BaseModel):
    comparison: CalcComparisonRead
    runs: CalcRunCompareResponse
