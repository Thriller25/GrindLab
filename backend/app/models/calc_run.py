import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base


class CalcRun(Base):
    __tablename__ = "calc_run"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    flowsheet_version_id = Column(UUID(as_uuid=True), ForeignKey("flowsheet_version.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    scenario_name = Column(String(255), nullable=True, default=None)
    comment = Column(Text, nullable=True, default=None)
    status = Column(String(50), nullable=False, default="success")
    started_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    request_json = Column(JSON, nullable=False)
    result_json = Column(JSON, nullable=False)
