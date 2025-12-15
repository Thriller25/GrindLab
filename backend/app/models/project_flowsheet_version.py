import uuid

from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db import Base
from app.models.project import Project
from app.models.flowsheet_version import FlowsheetVersion


class ProjectFlowsheetVersion(Base):
    __tablename__ = "project_flowsheet_version"

    project_id = Column(UUID(as_uuid=True), ForeignKey("project.id"), primary_key=True)
    flowsheet_version_id = Column(UUID(as_uuid=True), ForeignKey("flowsheet_version.id"), primary_key=True)

    project = relationship(Project, backref="flowsheet_links")
    flowsheet_version = relationship(FlowsheetVersion, backref="project_links")

    __table_args__ = (UniqueConstraint("project_id", "flowsheet_version_id", name="uq_project_flowsheet_version"),)
