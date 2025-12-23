import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class FlowsheetBase(BaseModel):
    plant_id: uuid.UUID
    name: str
    description: Optional[str] = None
    status: str = "DRAFT"


class FlowsheetCreate(FlowsheetBase):
    pass


class FlowsheetUpdate(BaseModel):
    plant_id: Optional[uuid.UUID] = None
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class FlowsheetRead(FlowsheetBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
