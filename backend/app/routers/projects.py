import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, and_
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.routers.auth import get_current_user
from app.schemas import (
    ProjectCreate,
    ProjectDetail,
    ProjectListResponse,
    ProjectRead,
    FlowsheetVersionRead,
    ProjectSummary,
    ProjectMemberAddRequest,
    ProjectMemberRead,
    ProjectDashboardResponse,
)
from app.schemas.user import UserRead
from app.schemas.calc_scenario import CalcScenarioRead
from app.schemas.calc_run import CalcRunListItem
from app.schemas.comment import CommentRead

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _ensure_project_exists_and_get(db: Session, project_id: uuid.UUID) -> models.Project:
    project = db.get(models.Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _check_project_read_access(db: Session, project: models.Project, user: models.User) -> None:
    if project.owner_user_id == user.id:
        return
    membership = (
        db.query(models.ProjectMember)
        .filter(models.ProjectMember.project_id == project.id, models.ProjectMember.user_id == user.id)
        .first()
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> ProjectRead:
    project = models.Project(
        name=payload.name,
        description=payload.description,
        owner_user_id=current_user.id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return ProjectRead.model_validate(project, from_attributes=True)


@router.get("/my", response_model=ProjectListResponse)
def get_my_projects(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> ProjectListResponse:
    query = db.query(models.Project).filter(models.Project.owner_user_id == current_user.id)
    total = query.count()
    items = query.order_by(models.Project.created_at.desc()).offset(offset).limit(limit).all()
    dto_items = [ProjectRead.model_validate(item, from_attributes=True) for item in items]
    return ProjectListResponse(items=dto_items, total=total)


@router.post(
    "/{project_id}/flowsheet-versions/{flowsheet_version_id}",
    status_code=status.HTTP_201_CREATED,
)
def attach_flowsheet_version_to_project(
    project_id: uuid.UUID,
    flowsheet_version_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project = _ensure_project_exists_and_get(db, project_id)
    if project.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    flowsheet_version = db.get(models.FlowsheetVersion, flowsheet_version_id)
    if flowsheet_version is None:
        raise HTTPException(status_code=404, detail="Flowsheet version not found")

    existing = (
        db.query(models.ProjectFlowsheetVersion)
        .filter(
            models.ProjectFlowsheetVersion.project_id == project_id,
            models.ProjectFlowsheetVersion.flowsheet_version_id == flowsheet_version_id,
        )
        .first()
    )
    if existing is None:
        link = models.ProjectFlowsheetVersion(
            project_id=project_id,
            flowsheet_version_id=flowsheet_version_id,
        )
        db.add(link)
        db.commit()

    return {"detail": "Attached"}


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project_detail(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> ProjectDetail:
    project = _ensure_project_exists_and_get(db, project_id)
    _check_project_read_access(db, project, current_user)

    links = (
        db.query(models.ProjectFlowsheetVersion)
        .filter(models.ProjectFlowsheetVersion.project_id == project_id)
        .all()
    )
    version_ids = [link.flowsheet_version_id for link in links]
    if version_ids:
        versions = (
            db.query(models.FlowsheetVersion)
            .filter(models.FlowsheetVersion.id.in_(version_ids))
            .all()
        )
    else:
        versions = []

    flowsheet_version_dtos = [FlowsheetVersionRead.model_validate(v, from_attributes=True) for v in versions]

    return ProjectDetail(
        id=project.id,
        name=project.name,
        description=project.description,
        owner_user_id=project.owner_user_id,
        created_at=project.created_at,
        flowsheet_versions=flowsheet_version_dtos,
    )


def _calculate_project_summary(
    db: Session, project: models.Project, flowsheet_version_ids: list[uuid.UUID], current_user: models.User
) -> ProjectSummary:
    _check_project_read_access(db, project, current_user)
    if not flowsheet_version_ids:
        return ProjectSummary(
            project=ProjectRead.model_validate(project, from_attributes=True),
            flowsheet_versions_total=0,
            scenarios_total=0,
            calc_runs_total=0,
            calc_runs_by_status={},
            comments_total=0,
            last_activity_at=None,
        )

    scenarios_total = (
        db.query(func.count(models.CalcScenario.id))
        .filter(models.CalcScenario.flowsheet_version_id.in_(flowsheet_version_ids))
        .scalar()
        or 0
    )

    calc_runs_total = (
        db.query(func.count(models.CalcRun.id))
        .filter(models.CalcRun.flowsheet_version_id.in_(flowsheet_version_ids))
        .scalar()
        or 0
    )

    status_rows = (
        db.query(models.CalcRun.status, func.count(models.CalcRun.id))
        .filter(models.CalcRun.flowsheet_version_id.in_(flowsheet_version_ids))
        .group_by(models.CalcRun.status)
        .all()
    )
    calc_runs_by_status = {status: count for status, count in status_rows if status is not None}

    scenario_ids = [
        row[0]
        for row in db.query(models.CalcScenario.id)
        .filter(models.CalcScenario.flowsheet_version_id.in_(flowsheet_version_ids))
        .all()
    ]
    run_ids = [
        row[0]
        for row in db.query(models.CalcRun.id)
        .filter(models.CalcRun.flowsheet_version_id.in_(flowsheet_version_ids))
        .all()
    ]

    comments_total = 0
    if scenario_ids:
        comments_total += (
            db.query(func.count(models.Comment.id))
            .filter(models.Comment.entity_type == "scenario", models.Comment.entity_id.in_(scenario_ids))
            .scalar()
            or 0
        )
    if run_ids:
        comments_total += (
            db.query(func.count(models.Comment.id))
            .filter(models.Comment.entity_type == "calc_run", models.Comment.entity_id.in_(run_ids))
            .scalar()
            or 0
        )

    scenario_last = (
        db.query(func.max(models.CalcScenario.created_at)).filter(models.CalcScenario.id.in_(scenario_ids)).scalar()
        if scenario_ids
        else None
    )
    run_last = (
        db.query(func.max(models.CalcRun.started_at)).filter(models.CalcRun.id.in_(run_ids)).scalar() if run_ids else None
    )

    comment_last_candidates = []
    if scenario_ids:
        comment_last_candidates.append(
            db.query(func.max(models.Comment.created_at))
            .filter(models.Comment.entity_type == "scenario", models.Comment.entity_id.in_(scenario_ids))
            .scalar()
        )
    if run_ids:
        comment_last_candidates.append(
            db.query(func.max(models.Comment.created_at))
            .filter(models.Comment.entity_type == "calc_run", models.Comment.entity_id.in_(run_ids))
            .scalar()
        )
    comment_last_candidates = [dt for dt in comment_last_candidates if dt is not None]
    comment_last = max(comment_last_candidates) if comment_last_candidates else None

    last_candidates = [dt for dt in (scenario_last, run_last, comment_last) if dt is not None]
    last_activity_at = max(last_candidates) if last_candidates else None

    return ProjectSummary(
        project=ProjectRead.model_validate(project, from_attributes=True),
        flowsheet_versions_total=len(flowsheet_version_ids),
        scenarios_total=scenarios_total,
        calc_runs_total=calc_runs_total,
        calc_runs_by_status=calc_runs_by_status,
        comments_total=comments_total,
        last_activity_at=last_activity_at,
    )


@router.get("/{project_id}/summary", response_model=ProjectSummary)
def get_project_summary(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> ProjectSummary:
    project = _ensure_project_exists_and_get(db, project_id)
    links = (
        db.query(models.ProjectFlowsheetVersion)
        .filter(models.ProjectFlowsheetVersion.project_id == project_id)
        .all()
    )
    flowsheet_version_ids = [link.flowsheet_version_id for link in links]
    return _calculate_project_summary(db, project, flowsheet_version_ids, current_user)


@router.get("/{project_id}/members", response_model=list[ProjectMemberRead])
def list_project_members(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> list[ProjectMemberRead]:
    project = _ensure_project_exists_and_get(db, project_id)
    _check_project_read_access(db, project, current_user)

    memberships = db.query(models.ProjectMember).filter(models.ProjectMember.project_id == project_id).all()
    result: list[ProjectMemberRead] = []
    for m in memberships:
        result.append(
            ProjectMemberRead(
                user=UserRead.model_validate(m.user, from_attributes=True),
                role=m.role,
                added_at=m.added_at,
            )
        )
    return result


@router.post("/{project_id}/members", response_model=ProjectMemberRead, status_code=status.HTTP_201_CREATED)
def add_project_member(
    project_id: uuid.UUID,
    payload: ProjectMemberAddRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> ProjectMemberRead:
    project = _ensure_project_exists_and_get(db, project_id)
    if project.owner_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == project.owner_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is already the project owner")

    existing = (
        db.query(models.ProjectMember)
        .filter(models.ProjectMember.project_id == project.id, models.ProjectMember.user_id == user.id)
        .first()
    )
    if existing:
        return ProjectMemberRead(
            user=UserRead.model_validate(user, from_attributes=True),
            role=existing.role,
            added_at=existing.added_at,
        )

    membership = models.ProjectMember(project_id=project.id, user_id=user.id, role=payload.role)
    db.add(membership)
    db.commit()
    db.refresh(membership)

    return ProjectMemberRead(
        user=UserRead.model_validate(user, from_attributes=True),
        role=membership.role,
        added_at=membership.added_at,
    )


@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_project_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project = _ensure_project_exists_and_get(db, project_id)
    if project.owner_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    membership = (
        db.query(models.ProjectMember)
        .filter(models.ProjectMember.project_id == project.id, models.ProjectMember.user_id == user_id)
        .first()
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project member not found")

    db.delete(membership)
    db.commit()
    return None


RECENT_RUNS_LIMIT = 10
RECENT_COMMENTS_LIMIT = 10


@router.get("/{project_id}/dashboard", response_model=ProjectDashboardResponse)
def get_project_dashboard(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> ProjectDashboardResponse:
    project = _ensure_project_exists_and_get(db, project_id)
    links = (
        db.query(models.ProjectFlowsheetVersion)
        .filter(models.ProjectFlowsheetVersion.project_id == project_id)
        .all()
    )
    flowsheet_version_ids = [link.flowsheet_version_id for link in links]
    summary = _calculate_project_summary(db, project, flowsheet_version_ids, current_user)
    _check_project_read_access(db, project, current_user)

    if flowsheet_version_ids:
        versions = (
            db.query(models.FlowsheetVersion)
            .filter(models.FlowsheetVersion.id.in_(flowsheet_version_ids))
            .all()
        )
    else:
        versions = []
    flowsheet_versions_dto = [FlowsheetVersionRead.model_validate(v, from_attributes=True) for v in versions]

    if flowsheet_version_ids:
        scenarios = (
            db.query(models.CalcScenario)
            .filter(models.CalcScenario.flowsheet_version_id.in_(flowsheet_version_ids))
            .all()
        )
    else:
        scenarios = []
    scenarios_dto = [CalcScenarioRead.model_validate(s, from_attributes=True) for s in scenarios]

    if flowsheet_version_ids:
        recent_runs = (
            db.query(models.CalcRun)
            .filter(models.CalcRun.flowsheet_version_id.in_(flowsheet_version_ids))
            .order_by(models.CalcRun.started_at.desc().nullslast())
            .limit(RECENT_RUNS_LIMIT)
            .all()
        )
    else:
        recent_runs = []
    recent_runs_dto = [CalcRunListItem.model_validate(r, from_attributes=True) for r in recent_runs]

    scenario_ids = [s.id for s in scenarios]
    run_ids = [r.id for r in recent_runs] if recent_runs else [
        row[0]
        for row in db.query(models.CalcRun.id)
        .filter(models.CalcRun.flowsheet_version_id.in_(flowsheet_version_ids))
        .all()
    ] if flowsheet_version_ids else []

    recent_comments: list[models.Comment] = []
    conditions = []
    if scenario_ids:
        conditions.append(and_(models.Comment.entity_type == "scenario", models.Comment.entity_id.in_(scenario_ids)))
    if run_ids:
        conditions.append(and_(models.Comment.entity_type == "calc_run", models.Comment.entity_id.in_(run_ids)))
    if conditions:
        recent_comments = (
            db.query(models.Comment)
            .filter(or_(*conditions))
            .order_by(models.Comment.created_at.desc())
            .limit(RECENT_COMMENTS_LIMIT)
            .all()
        )
    recent_comments_dto = [CommentRead.model_validate(c, from_attributes=True) for c in recent_comments]

    return ProjectDashboardResponse(
        project=ProjectRead.model_validate(project, from_attributes=True),
        summary=summary,
        flowsheet_versions=flowsheet_versions_dto,
        scenarios=scenarios_dto,
        recent_calc_runs=recent_runs_dto,
        recent_comments=recent_comments_dto,
    )
