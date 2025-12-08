import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base


class CalcRun(Base):
    __tablename__ = "calc_run"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    flowsheet_version_id = Column(UUID(as_uuid=True), ForeignKey("flowsheet_version.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    request_json = Column(JSON, nullable=False)
    result_json = Column(JSON, nullable=False)
