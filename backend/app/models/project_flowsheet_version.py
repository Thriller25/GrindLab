from app.db import Base
from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship


class ProjectFlowsheetVersion(Base):
    __tablename__ = "project_flowsheet_version"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("project.id"), nullable=False)
    flowsheet_version_id = Column(
        UUID(as_uuid=True), ForeignKey("flowsheet_version.id"), nullable=False
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    project = relationship(
        "Project",
        back_populates="flowsheet_version_links",
    )
    flowsheet_version = relationship(
        "FlowsheetVersion",
        back_populates="project_links",
    )

    __table_args__ = (
        UniqueConstraint("project_id", "flowsheet_version_id", name="uq_project_flowsheet_version"),
    )
