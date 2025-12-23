import uuid

from app.db import Base
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import relationship


class FlowsheetVersion(Base):
    __tablename__ = "flowsheet_version"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    flowsheet_id = Column(UUID(as_uuid=True), ForeignKey("flowsheet.id"), nullable=False)
    version_label = Column(String(64), nullable=False)
    # Status stored as string, but should be one of: DRAFT, ACTIVE, ARCHIVED
    status = Column(String(16), nullable=False, default="DRAFT")
    is_active = Column(Boolean, nullable=False, default=False)
    comment = Column(Text, nullable=True)
    created_by = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    flowsheet = relationship("Flowsheet", back_populates="versions")
    units = relationship("Unit", back_populates="flowsheet_version")
    calc_runs = relationship("CalcRun", back_populates="flowsheet_version")
    calc_scenarios = relationship("CalcScenario", back_populates="flowsheet_version")
    project_links = relationship(
        "ProjectFlowsheetVersion",
        back_populates="flowsheet_version",
        cascade="all, delete-orphan",
    )
    projects = association_proxy("project_links", "project")
