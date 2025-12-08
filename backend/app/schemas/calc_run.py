from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel


class CalcRunRead(BaseModel):
    id: UUID
    flowsheet_version_id: UUID
    created_at: datetime
    scenario_name: Optional[str] = None
    comment: Optional[str] = None
    status: str
    started_at: datetime
    finished_at: datetime
    request_json: Dict[str, Any]
    result_json: Dict[str, Any]

    class Config:
        orm_mode = True
