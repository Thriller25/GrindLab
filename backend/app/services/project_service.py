from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app import models


def attach_flowsheet_version_to_project(
    db: Session,
    project_id: int,
    flowsheet_version_id: uuid.UUID,
    *,
    project: Optional[models.Project] = None,
    flowsheet_version: Optional[models.FlowsheetVersion] = None,
) -> models.ProjectFlowsheetVersion:
    """
    Link a flowsheet version to a project if not already linked.
    """
    project = project or db.get(models.Project, project_id)
    if project is None:
        raise ValueError("Project not found")

    flowsheet_version = flowsheet_version or db.get(models.FlowsheetVersion, flowsheet_version_id)
    if flowsheet_version is None:
        raise ValueError("Flowsheet version not found")

    existing = (
        db.query(models.ProjectFlowsheetVersion)
        .filter(
            models.ProjectFlowsheetVersion.project_id == project.id,
            models.ProjectFlowsheetVersion.flowsheet_version_id == flowsheet_version.id,
        )
        .first()
    )
    if existing:
        return existing

    link = models.ProjectFlowsheetVersion(
        project_id=project.id,
        flowsheet_version_id=flowsheet_version.id,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link
