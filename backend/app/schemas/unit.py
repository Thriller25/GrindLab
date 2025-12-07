import uuid
from typing import Any, Optional

from pydantic import BaseModel


class UnitBase(BaseModel):
    flowsheet_version_id: uuid.UUID
    equipment_type_id: Optional[uuid.UUID] = None
    name: str
    tag: Optional[str] = None
    position_x: Optional[int] = None
    position_y: Optional[int] = None
    order_index: Optional[int] = None
    passport_params_json: Optional[dict[str, Any]] = None
    limits_json: Optional[dict[str, Any]] = None
    participates_in_opt: bool = True
    is_active: bool = True


class UnitCreate(UnitBase):
    pass


class UnitUpdate(BaseModel):
    flowsheet_version_id: Optional[uuid.UUID] = None
    equipment_type_id: Optional[uuid.UUID] = None
    name: Optional[str] = None
    tag: Optional[str] = None
    position_x: Optional[int] = None
    position_y: Optional[int] = None
    order_index: Optional[int] = None
    passport_params_json: Optional[dict[str, Any]] = None
    limits_json: Optional[dict[str, Any]] = None
    participates_in_opt: Optional[bool] = None
    is_active: Optional[bool] = None


class UnitRead(UnitBase):
    id: uuid.UUID

    class Config:
        orm_mode = True
