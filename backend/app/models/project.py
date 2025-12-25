from app.db import Base
from app.models.plant import Plant
from app.models.user import User
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import relationship


class Project(Base):
    __tablename__ = "project"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)
    plant_id = Column(UUID(as_uuid=True), ForeignKey("plant.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    owner = relationship(User, backref="projects")
    plant = relationship(Plant, backref="projects")
    calc_runs = relationship("CalcRun", back_populates="project")
    flowsheet_version_links = relationship(
        "ProjectFlowsheetVersion",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    flowsheet_versions = association_proxy("flowsheet_version_links", "flowsheet_version")
    calc_scenarios = relationship("CalcScenario", back_populates="project")
