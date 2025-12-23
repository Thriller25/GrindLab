import uuid

from app.db import Base
from sqlalchemy import Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship


class Flowsheet(Base):
    __tablename__ = "flowsheet"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plant_id = Column(UUID(as_uuid=True), ForeignKey("plant.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    # Status stored as string, but should be one of: DRAFT, ACTIVE, ARCHIVED
    status = Column(String(16), nullable=False, default="DRAFT")
    created_by = Column(UUID(as_uuid=True), nullable=True)
    updated_by = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    plant = relationship("Plant", back_populates="flowsheets")
    versions = relationship("FlowsheetVersion", back_populates="flowsheet")
