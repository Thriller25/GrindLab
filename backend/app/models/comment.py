import uuid

from app.db import Base
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship


class Comment(Base):
    __tablename__ = "comment"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(Integer, ForeignKey("project.id"), nullable=False)
    scenario_id = Column(UUID(as_uuid=True), ForeignKey("calc_scenario.id"), nullable=True)
    calc_run_id = Column(UUID(as_uuid=True), ForeignKey("calc_run.id"), nullable=True)
    author = Column(String(255), nullable=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    project = relationship("Project")
    scenario = relationship("CalcScenario")
    calc_run = relationship("CalcRun")

    __table_args__ = (
        CheckConstraint(
            "(scenario_id IS NOT NULL AND calc_run_id IS NULL) OR "
            "(scenario_id IS NULL AND calc_run_id IS NOT NULL)",
            name="comment_single_target",
        ),
    )
