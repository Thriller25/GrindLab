from datetime import datetime
from typing import Any, Dict
from uuid import UUID

from pydantic import BaseModel


class CalcRunRead(BaseModel):
    id: UUID
    flowsheet_version_id: UUID
    created_at: datetime
    request_json: Dict[str, Any]
    result_json: Dict[str, Any]

    class Config:
        orm_mode = True
