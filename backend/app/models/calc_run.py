import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db import Base


class CalcRun(Base):
    __tablename__ = "calc_run"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    flowsheet_version_id = Column(UUID(as_uuid=True), ForeignKey("flowsheet_version.id"), nullable=False)
    scenario_name = Column(String(255), nullable=True, default=None)
    comment = Column(Text, nullable=True, default=None)
    status = Column(String(32), nullable=False, default="pending")
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(String, nullable=True, default=None)
    input_json = Column(JSON, nullable=True)
    result_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    flowsheet_version = relationship("FlowsheetVersion", back_populates="calc_runs")
