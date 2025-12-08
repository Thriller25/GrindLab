from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CalcRunCreate(BaseModel):
    flowsheet_version_id: UUID
    scenario_name: Optional[str] = None
    comment: Optional[str] = None
    input_json: Optional[Dict[str, Any]] = None


class CalcRunRead(BaseModel):
    id: UUID
    flowsheet_version_id: UUID
    scenario_name: Optional[str] = None
    comment: Optional[str] = None
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error_message: Optional[str] = None
    input_json: Optional[Dict[str, Any]] = None
    result_json: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CalcRunListItem(BaseModel):
    id: UUID
    flowsheet_version_id: UUID
    scenario_name: Optional[str] = None
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    comment: Optional[str] = None
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


class CalcRunListResponse(BaseModel):
    items: list[CalcRunListItem]
    total: int
