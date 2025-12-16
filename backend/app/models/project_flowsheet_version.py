from sqlalchemy import Column, ForeignKey, UniqueConstraint, Integer, DateTime, func
from sqlalchemy.orm import relationship

from app.db import Base


class ProjectFlowsheetVersion(Base):
    __tablename__ = "project_flowsheet_version"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("project.id"), nullable=False)
    flowsheet_version_id = Column(Integer, ForeignKey("flowsheet_version.id"), nullable=False)
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
        overlaps="flowsheet_versions,projects,project_links",
    )
    flowsheet_version = relationship(
        "FlowsheetVersion",
        back_populates="project_links",
        overlaps="projects,flowsheet_versions,project",
    )

    __table_args__ = (UniqueConstraint("project_id", "flowsheet_version_id", name="uq_project_flowsheet_version"),)
