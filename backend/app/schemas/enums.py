# Enums for GrindLab
from enum import Enum


class CalcRunStatus(str, Enum):
    """Status of calculation run"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class FlowsheetStatus(str, Enum):
    """Status of flowsheet"""

    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class ProjectMemberRole(str, Enum):
    """Role of project member"""

    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


__all__ = [
    "CalcRunStatus",
    "FlowsheetStatus",
    "ProjectMemberRole",
]
