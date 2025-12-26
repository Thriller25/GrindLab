from app.db import Base
from app.models.project import Project
from app.models.user import User
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship


class ProjectMember(Base):
    __tablename__ = "project_member"

    project_id = Column(Integer, ForeignKey("project.id"), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), primary_key=True)
    role = Column(String(50), nullable=False, default="editor")
    added_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    project = relationship(Project, backref="members")
    user = relationship(User, backref="project_memberships")
