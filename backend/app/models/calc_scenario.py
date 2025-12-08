import uuid

from sqlalchemy import Column, DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db import Base


class CalcScenario(Base):
    __tablename__ = "calc_scenario"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    flowsheet_version_id = Column(UUID(as_uuid=True), ForeignKey("flowsheet_version.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    default_input_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    flowsheet_version = relationship("FlowsheetVersion", back_populates="calc_scenarios")
