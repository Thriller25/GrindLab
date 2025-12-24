import uuid

from app.db import Base
from sqlalchemy import JSON, Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship


class Unit(Base):
    __tablename__ = "unit"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    flowsheet_version_id = Column(
        UUID(as_uuid=True), ForeignKey("flowsheet_version.id"), nullable=False
    )
    equipment_type_id = Column(UUID(as_uuid=True), nullable=True)
    name = Column(String(255), nullable=False)
    tag = Column(String(255), nullable=True)
    position_x = Column(Integer, nullable=True)
    position_y = Column(Integer, nullable=True)
    order_index = Column(Integer, nullable=True)
    passport_params_json = Column(JSON, nullable=True)
    limits_json = Column(JSON, nullable=True)
    participates_in_opt = Column(Boolean, nullable=False, default=True)
    is_active = Column(Boolean, nullable=False, default=True)

    flowsheet_version = relationship("FlowsheetVersion", back_populates="units")
