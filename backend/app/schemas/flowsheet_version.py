import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class FlowsheetVersionBase(BaseModel):
    flowsheet_id: uuid.UUID
    version_label: str
    status: str = "DRAFT"
    is_active: bool = False
    comment: Optional[str] = None


class FlowsheetVersionCreate(FlowsheetVersionBase):
    pass


class FlowsheetVersionUpdate(BaseModel):
    flowsheet_id: Optional[uuid.UUID] = None
    version_label: Optional[str] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None
    comment: Optional[str] = None


class FlowsheetVersionRead(FlowsheetVersionBase):
    id: uuid.UUID
    created_at: datetime

    class Config:
        orm_mode = True


class FlowsheetVersionCloneRequest(BaseModel):
    new_version_name: Optional[str] = None
    clone_scenarios: bool = True


class FlowsheetVersionCloneResponse(BaseModel):
    flowsheet_version: FlowsheetVersionRead
    scenarios: list["CalcScenarioRead"]

    model_config = {"from_attributes": True}


# Late import to avoid circular dependency in type checkers
from app.schemas.calc_scenario import CalcScenarioRead  # noqa: E402
