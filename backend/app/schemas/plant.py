import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class PlantBase(BaseModel):
    name: str
    code: Optional[str] = None
    company: Optional[str] = None
    is_active: bool = True


class PlantCreate(PlantBase):
    pass


class PlantUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    company: Optional[str] = None
    is_active: Optional[bool] = None


class PlantRead(PlantBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
