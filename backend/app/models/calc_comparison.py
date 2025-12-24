import uuid
from typing import List

from app.db import Base
from sqlalchemy import JSON, Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship


class CalcComparison(Base):
    __tablename__ = "calc_comparison"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    flowsheet_version_id = Column(
        UUID(as_uuid=True), ForeignKey("flowsheet_version.id"), nullable=False
    )
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    run_ids_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    flowsheet_version = relationship("FlowsheetVersion")

    @property
    def run_ids(self) -> List[uuid.UUID]:
        if not self.run_ids_json:
            return []
        return [uuid.UUID(str(value)) for value in self.run_ids_json]
