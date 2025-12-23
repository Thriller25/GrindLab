import uuid
from datetime import datetime, timezone
from typing import Tuple

from app import models
from app.core.exceptions import raise_bad_request, raise_not_found, raise_permission_denied
from app.db import get_db
from app.routers.auth import get_current_user_optional
from app.schemas import CommentCreate, CommentListResponse, CommentRead
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api", tags=["comments"])

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


def _get_project_or_404(db: Session, project_id: str | int) -> models.Project:
    try:
        project_pk = int(project_id)
    except (TypeError, ValueError):
        raise_not_found("Project", project_id, f"Invalid project ID format: '{project_id}'")
    project = db.get(models.Project, project_pk)
    if project is None:
        raise_not_found("Project", project_pk)
    return project


def _check_project_read_access(
    db: Session, project: models.Project, user: models.User | None
) -> None:
    if project.owner_user_id is None:
        return
    if user is None:
        raise_permission_denied(
            action=f"view comments for project '{project.name}' (login required)"
        )
    if project.owner_user_id == user.id:
        return
    membership = (
        db.query(models.ProjectMember)
        .filter(
            models.ProjectMember.project_id == project.id, models.ProjectMember.user_id == user.id
        )
        .first()
    )
    if membership is None:
        raise_permission_denied(action=f"view comments for project '{project.name}'")


def _check_project_write_access(
    db: Session, project: models.Project, user: models.User | None
) -> None:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to add comments",
        )
    _check_project_read_access(db, project, user)


def _load_target(
    db: Session,
    project: models.Project,
    scenario_id: uuid.UUID | None,
    calc_run_id: uuid.UUID | None,
) -> Tuple[models.CalcScenario | None, models.CalcRun | None]:
    if scenario_id and calc_run_id:
        raise_bad_request("Provide only one target: either scenario_id or calc_run_id")
    if not scenario_id and not calc_run_id:
        raise_bad_request("Either scenario_id or calc_run_id is required")

    scenario = None
    calc_run = None
    if scenario_id:
        scenario = db.get(models.CalcScenario, scenario_id)
        if scenario is None:
            raise_not_found("CalcScenario", scenario_id)
        if scenario.project_id != project.id:
            raise_bad_request(
                f"Scenario '{scenario_id}' does not belong to project '{project.name}'"
            )
    if calc_run_id:
        calc_run = db.get(models.CalcRun, calc_run_id)
        if calc_run is None:
            raise_not_found("CalcRun", calc_run_id)
        if calc_run.project_id is None:
            raise_bad_request(f"CalcRun '{calc_run_id}' is not linked to any project")
        if calc_run.project_id != project.id:
            raise_bad_request(
                f"CalcRun '{calc_run_id}' does not belong to project '{project.name}'"
            )
    return scenario, calc_run


def _list_comments(
    db: Session,
    project: models.Project,
    *,
    scenario_id: uuid.UUID | None = None,
    calc_run_id: uuid.UUID | None = None,
    limit: int,
) -> CommentListResponse:
    query = db.query(models.Comment).filter(models.Comment.project_id == project.id)
    if scenario_id:
        query = query.filter(models.Comment.scenario_id == scenario_id)
    if calc_run_id:
        query = query.filter(models.Comment.calc_run_id == calc_run_id)

    total = query.with_entities(func.count(models.Comment.id)).scalar() or 0
    comments = (
        query.order_by(models.Comment.created_at.desc(), models.Comment.id.desc())
        .limit(limit)
        .all()
    )
    items = [CommentRead.model_validate(comment, from_attributes=True) for comment in comments]
    return CommentListResponse(items=items, total=total)


@router.get("/projects/{project_id}/comments", response_model=CommentListResponse)
def list_project_comments(
    project_id: str,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> CommentListResponse:
    project = _get_project_or_404(db, project_id)
    _check_project_read_access(db, project, current_user)
    return _list_comments(db, project, limit=limit)


@router.post(
    "/projects/{project_id}/comments",
    response_model=CommentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_project_comment(
    project_id: str,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> CommentRead:
    project = _get_project_or_404(db, project_id)
    _check_project_write_access(db, project, current_user)
    scenario, calc_run = _load_target(db, project, payload.scenario_id, payload.calc_run_id)

    author_value = payload.author or getattr(current_user, "email", None) or "anonymous"
    comment = models.Comment(
        project_id=project.id,
        scenario_id=scenario.id if scenario else None,
        calc_run_id=calc_run.id if calc_run else None,
        author=author_value,
        text=payload.text,
        created_at=datetime.now(timezone.utc),
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return CommentRead.model_validate(comment, from_attributes=True)


@router.get("/scenarios/{scenario_id}/comments", response_model=CommentListResponse)
def list_scenario_comments(
    scenario_id: uuid.UUID,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> CommentListResponse:
    scenario = db.get(models.CalcScenario, scenario_id)
    if scenario is None:
        raise_not_found("CalcScenario", scenario_id)
    project = _get_project_or_404(db, scenario.project_id)
    _check_project_read_access(db, project, current_user)
    return _list_comments(db, project, scenario_id=scenario.id, limit=limit)


@router.get("/calc-runs/{run_id}/comments", response_model=CommentListResponse)
def list_calc_run_comments(
    run_id: uuid.UUID,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> CommentListResponse:
    calc_run = db.get(models.CalcRun, run_id)
    if calc_run is None:
        raise_not_found("CalcRun", run_id)
    if calc_run.project_id is None:
        raise_bad_request(f"CalcRun '{run_id}' is not linked to any project")
    project = _get_project_or_404(db, calc_run.project_id)
    _check_project_read_access(db, project, current_user)
    return _list_comments(db, project, calc_run_id=calc_run.id, limit=limit)
