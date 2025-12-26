from app.db import Base
from app.models.user import User
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship


class UserFavorite(Base):
    __tablename__ = "user_favorite"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship(User, backref="favorites")

    __table_args__ = (
        UniqueConstraint("user_id", "entity_type", "entity_id", name="uq_user_favorite"),
    )
