import uuid
from sqlalchemy import Column, String, Text, Boolean, DateTime, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db import Base


class FlowsheetVersion(Base):
    __tablename__ = "flowsheet_version"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    flowsheet_id = Column(UUID(as_uuid=True), ForeignKey("flowsheet.id"), nullable=False)
    version_label = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, default="DRAFT")
    is_active = Column(Boolean, nullable=False, default=False)
    comment = Column(Text, nullable=True)
    created_by = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    flowsheet = relationship("Flowsheet", back_populates="versions")
    units = relationship("Unit", back_populates="flowsheet_version")
    calc_runs = relationship("CalcRun", back_populates="flowsheet_version")
