import uuid

from app import models
from app.db import get_db
from app.routers.auth import get_current_user, get_current_user_optional
from app.schemas import (
    CalcRunKpiDiffSummary,
    CalcRunKpiSummary,
    FlowsheetVersionRead,
    GrindMvpRunSummary,
    PaginatedResponse,
    ProjectCreate,
    ProjectDashboardResponse,
    ProjectDetail,
    ProjectFlowsheetSummary,
    ProjectFlowsheetVersionRead,
    ProjectListResponse,
    ProjectMemberAddRequest,
    ProjectMemberRead,
    ProjectRead,
    ProjectSummary,
)
from app.schemas.calc_run import CalcRunListItem
from app.schemas.calc_scenario import CalcScenarioRead
from app.schemas.comment import CommentRead
from app.schemas.user import UserRead
from app.services.project_service import (
    attach_flowsheet_version_to_project as attach_link_to_project,
)
from app.services.run_metrics import (
    extract_kpi,
    extract_model_version,
    find_baseline_run_for_version,
    find_best_project_run,
    is_grind_mvp_run,
)
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=PaginatedResponse[ProjectRead])
def list_projects(
    plant_id: uuid.UUID | None = Query(default=None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_optional),
) -> PaginatedResponse[ProjectRead]:
    """
    List projects with pagination.

    - **skip**: Number of items to skip (default: 0)
    - **limit**: Number of items to return (default: 20, max: 100)
    - **plant_id**: Optional filter by plant ID
    """
    # Start with base query
    base_query = db.query(models.Project)
    if plant_id:
        base_query = base_query.filter(models.Project.plant_id == plant_id)

    # Count total BEFORE joinedload
    total = base_query.count()

    # Apply joinedload to prevent N+1 queries on actual data fetch
    query = base_query.options(
        joinedload(models.Project.owner),
        joinedload(models.Project.plant),
    )

    # Apply pagination
    projects = query.order_by(models.Project.created_at.desc()).offset(skip).limit(limit).all()

    return PaginatedResponse(
        total=total,
        skip=skip,
        limit=limit,
        items=[ProjectRead.model_validate(p, from_attributes=True) for p in projects],
    )


def _ensure_project_exists_and_get(db: Session, project_id) -> models.Project:
    try:
        project_pk = int(project_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    project = db.get(models.Project, project_pk)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _build_grind_mvp_summary(run: models.CalcRun) -> GrindMvpRunSummary:
    input_json = run.input_json if isinstance(run.input_json, dict) else {}
    result_json = run.result_json if isinstance(run.result_json, dict) else {}
    kpi = result_json.get("kpi") if isinstance(result_json, dict) else None
    throughput = kpi.get("throughput_tph") if isinstance(kpi, dict) else None
    product_p80 = kpi.get("product_p80_mm") if isinstance(kpi, dict) else None
    spec_energy = kpi.get("specific_energy_kwh_per_t") if isinstance(kpi, dict) else None

    return GrindMvpRunSummary(
        id=run.id,
        created_at=run.created_at,
        model_version=extract_model_version(run) or "grind_mvp_v1",
        plant_id=(
            str(input_json.get("plant_id")) if input_json.get("plant_id") is not None else None
        ),
        flowsheet_version_id=(
            str(run.flowsheet_version_id) if run.flowsheet_version_id is not None else None
        ),
        scenario_name=run.scenario_name or input_json.get("scenario_name"),
        project_id=getattr(run, "project_id", None),
        project_name=getattr(run.project, "name", None) if getattr(run, "project", None) else None,
        comment=run.comment,
        throughput_tph=throughput,
        product_p80_mm=product_p80,
        specific_energy_kwhpt=spec_energy,
    )


def _build_kpi_summary(run: models.CalcRun) -> CalcRunKpiSummary | None:
    kpi = extract_kpi(run)
    if not kpi:
        return None
    return CalcRunKpiSummary(
        id=str(run.id),
        created_at=run.created_at,
        throughput_tph=kpi.get("throughput_tph"),
        product_p80_mm=kpi.get("product_p80_mm"),
        specific_energy_kwhpt=kpi.get("specific_energy_kwh_per_t"),
        circulating_load_pct=kpi.get("circulating_load_percent"),
        power_use_pct=kpi.get("mill_utilization_percent"),
    )


def _find_latest_grind_mvp_run(
    db: Session, project_id: int, flowsheet_version_id: uuid.UUID
) -> models.CalcRun | None:
    runs = (
        db.query(models.CalcRun)
        .filter(
            models.CalcRun.project_id == project_id,
            models.CalcRun.flowsheet_version_id == flowsheet_version_id,
        )
        .order_by(
            models.CalcRun.started_at.desc().nullslast(),
            models.CalcRun.created_at.desc(),
            models.CalcRun.id.desc(),
        )
        .all()
    )
    for run in runs:
        if is_grind_mvp_run(run):
            return run
    return None


def _find_grind_mvp_runs(
    db: Session, project_id: int, flowsheet_version_id: uuid.UUID
) -> list[models.CalcRun]:
    runs = (
        db.query(models.CalcRun)
        .filter(
            models.CalcRun.project_id == project_id,
            models.CalcRun.flowsheet_version_id == flowsheet_version_id,
        )
        .order_by(
            models.CalcRun.started_at.desc().nullslast(),
            models.CalcRun.created_at.desc(),
            models.CalcRun.id.desc(),
        )
        .all()
    )
    return [run for run in runs if is_grind_mvp_run(run)]


def _load_project_flowsheet_versions(
    db: Session, project_id: int
) -> list[ProjectFlowsheetVersionRead]:
    rows = (
        db.query(models.ProjectFlowsheetVersion, models.FlowsheetVersion, models.Flowsheet)
        .join(
            models.FlowsheetVersion,
            models.ProjectFlowsheetVersion.flowsheet_version_id == models.FlowsheetVersion.id,
        )
        .join(models.Flowsheet, models.Flowsheet.id == models.FlowsheetVersion.flowsheet_id)
        .filter(models.ProjectFlowsheetVersion.project_id == project_id)
        .all()
    )
    result: list[ProjectFlowsheetVersionRead] = []
    for link, version, flowsheet in rows:
        updated_at = (
            getattr(version, "updated_at", None)
            or getattr(link, "updated_at", None)
            or version.created_at
        )
        result.append(
            ProjectFlowsheetVersionRead(
                id=link.id or version.id,
                flowsheet_version_id=version.id,
                flowsheet_name=flowsheet.name,
                flowsheet_version_label=version.version_label,
                model_name="grind_mvp_v1",
                plant_id=flowsheet.plant_id,
                updated_at=updated_at,
            )
        )
    return result


def _get_project_runs(
    db: Session, project_id: int, flowsheet_version_id: uuid.UUID
) -> list[models.CalcRun]:
    return (
        db.query(models.CalcRun)
        .outerjoin(models.CalcScenario, models.CalcScenario.id == models.CalcRun.scenario_id)
        .filter(
            models.CalcRun.project_id == project_id,
            models.CalcRun.flowsheet_version_id == flowsheet_version_id,
            models.CalcRun.status == "success",
            or_(models.CalcScenario.is_baseline.is_(False), models.CalcRun.scenario_id.is_(None)),
        )
        .all()
    )


def _build_project_detail(db: Session, project: models.Project) -> ProjectDetail:
    flowsheet_versions = _load_project_flowsheet_versions(db, project.id)

    rows = (
        db.query(
            models.ProjectFlowsheetVersion, models.FlowsheetVersion, models.Flowsheet, models.Plant
        )
        .join(
            models.FlowsheetVersion,
            models.ProjectFlowsheetVersion.flowsheet_version_id == models.FlowsheetVersion.id,
        )
        .join(models.Flowsheet, models.Flowsheet.id == models.FlowsheetVersion.flowsheet_id)
        .outerjoin(models.Plant, models.Plant.id == models.Flowsheet.plant_id)
        .filter(models.ProjectFlowsheetVersion.project_id == project.id)
        .all()
    )

    summaries: list[ProjectFlowsheetSummary] = []
    for _, version, flowsheet, plant in rows:
        baseline = find_baseline_run_for_version(db, version.id, project.id)
        runs_for_project = _get_project_runs(db, project.id, version.id)
        best = find_best_project_run(db, project.id, version.id) if runs_for_project else None
        baseline_summary = _build_kpi_summary(baseline) if baseline else None
        best_summary = _build_kpi_summary(best) if best else None
        diff_summary: CalcRunKpiDiffSummary | None = None
        if baseline_summary and best_summary:
            diff_summary = CalcRunKpiDiffSummary(
                throughput_tph_delta=(
                    None
                    if baseline_summary.throughput_tph is None
                    or best_summary.throughput_tph is None
                    else best_summary.throughput_tph - baseline_summary.throughput_tph
                ),
                specific_energy_kwhpt_delta=(
                    None
                    if baseline_summary.specific_energy_kwhpt is None
                    or best_summary.specific_energy_kwhpt is None
                    else best_summary.specific_energy_kwhpt - baseline_summary.specific_energy_kwhpt
                ),
                p80_mm_delta=(
                    None
                    if baseline_summary.product_p80_mm is None
                    or best_summary.product_p80_mm is None
                    else best_summary.product_p80_mm - baseline_summary.product_p80_mm
                ),
                circulating_load_pct_delta=(
                    None
                    if baseline_summary.circulating_load_pct is None
                    or best_summary.circulating_load_pct is None
                    else best_summary.circulating_load_pct - baseline_summary.circulating_load_pct
                ),
                power_use_pct_delta=(
                    None
                    if baseline_summary.power_use_pct is None or best_summary.power_use_pct is None
                    else best_summary.power_use_pct - baseline_summary.power_use_pct
                ),
            )

        summaries.append(
            ProjectFlowsheetSummary(
                flowsheet_id=flowsheet.id,
                flowsheet_name=flowsheet.name,
                flowsheet_version_id=version.id,
                flowsheet_version_label=version.version_label,
                model_code="grind_mvp_v1",
                plant_name=getattr(plant, "name", None),
                has_runs=bool(runs_for_project),
                baseline_run=baseline_summary,
                best_project_run=best_summary,
                diff_vs_baseline=diff_summary,
            )
        )

    return ProjectDetail(
        id=project.id,
        name=project.name,
        description=project.description,
        owner_user_id=project.owner_user_id,
        plant_id=project.plant_id,
        created_at=project.created_at,
        updated_at=project.updated_at,
        flowsheet_versions=flowsheet_versions,
        flowsheet_summaries=summaries,
    )


def _check_project_read_access(
    db: Session, project: models.Project, user: models.User | None
) -> None:
    # Public (ownerless) projects are readable by anyone.
    if project.owner_user_id is None:
        return
    if user is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> ProjectRead:
    project = models.Project(
        name=payload.name,
        description=payload.description,
        owner_user_id=getattr(current_user, "id", None),
        plant_id=payload.plant_id if payload.plant_id not in ("", None) else None,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return ProjectRead.model_validate(project, from_attributes=True)


@router.get("/my", response_model=ProjectListResponse)
def get_my_projects(
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> ProjectListResponse:
    query = db.query(models.Project)
    if current_user is None:
        query = query.filter(models.Project.owner_user_id.is_(None))
    else:
        query = query.filter(models.Project.owner_user_id == current_user.id)
    total = query.count()
    items = query.order_by(models.Project.created_at.desc()).offset(offset).limit(limit).all()
    dto_items = [ProjectRead.model_validate(item, from_attributes=True) for item in items]
    return ProjectListResponse(items=dto_items, total=total)


@router.post("/demo-seed", response_model=ProjectRead, status_code=status.HTTP_200_OK)
def seed_demo_project(
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> ProjectRead:
    from app.demo_seed import (
        _get_or_create_demo_user,
        seed_grind_mvp_runs,
        seed_plants_and_flowsheets,
        seed_project_flowsheet_links,
        seed_projects,
    )

    _get_or_create_demo_user(db)
    plants, versions = seed_plants_and_flowsheets(db)
    gold_plant = plants.get("GOLD-1")
    projects = seed_projects(db, gold_plant_id=gold_plant.id if gold_plant else None)

    demo_versions = [versions.get("gold_base_v1"), versions.get("gold_opt_v2")]
    demo_versions = [v for v in demo_versions if v is not None]
    if projects and demo_versions:
        seed_project_flowsheet_links(db, projects, demo_versions)
        seed_grind_mvp_runs(db, projects, demo_versions)

    if not projects:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create demo project",
        )

    project = projects[0]
    db.refresh(project)
    return ProjectRead.model_validate(project, from_attributes=True)


@router.post(
    "/{project_id}/flowsheet-versions/{flowsheet_version_id}",
    response_model=ProjectDetail,
    status_code=status.HTTP_200_OK,
)
def attach_flowsheet_version_to_project(
    project_id: str,
    flowsheet_version_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
):
    project = _ensure_project_exists_and_get(db, project_id)
    if project.owner_user_id != getattr(current_user, "id", None):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    attach_link_to_project(db, project.id, flowsheet_version_id, project=project)
    db.refresh(project)
    return _build_project_detail(db, project)


@router.get(
    "/{project_id}/flowsheet-versions/{flowsheet_version_id}/latest-grind-mvp-run",
    response_model=GrindMvpRunSummary,
)
def get_latest_grind_mvp_run_for_project_and_version(
    project_id: str,
    flowsheet_version_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> GrindMvpRunSummary:
    project = _ensure_project_exists_and_get(db, project_id)
    _check_project_read_access(db, project, current_user)
    run = _find_latest_grind_mvp_run(db, project.id, flowsheet_version_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No grind_mvp_v1 runs found for this project and flowsheet version",
        )
    return _build_grind_mvp_summary(run)


@router.get(
    "/{project_id}/flowsheet-versions/{flowsheet_version_id}/grind-mvp-runs",
    response_model=list[GrindMvpRunSummary],
)
def list_grind_mvp_runs_for_project_and_version(
    project_id: str,
    flowsheet_version_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> list[GrindMvpRunSummary]:
    project = _ensure_project_exists_and_get(db, project_id)
    _check_project_read_access(db, project, current_user)
    runs = _find_grind_mvp_runs(db, project.id, flowsheet_version_id)
    if not runs:
        return []
    return [_build_grind_mvp_summary(run) for run in runs]


@router.delete(
    "/{project_id}/flowsheet-versions/{flowsheet_version_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def detach_flowsheet_version_from_project(
    project_id: str,
    flowsheet_version_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
):
    project = _ensure_project_exists_and_get(db, project_id)
    if project.owner_user_id != getattr(current_user, "id", None):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    link = (
        db.query(models.ProjectFlowsheetVersion)
        .filter(
            models.ProjectFlowsheetVersion.project_id == project.id,
            models.ProjectFlowsheetVersion.flowsheet_version_id == flowsheet_version_id,
        )
        .first()
    )
    if link:
        db.delete(link)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project_detail(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user_optional),
) -> ProjectDetail:
    project = _ensure_project_exists_and_get(db, project_id)
    _check_project_read_access(db, project, current_user)
    return _build_project_detail(db, project)


def _calculate_project_summary(
    db: Session,
    project: models.Project,
    flowsheet_version_ids: list[uuid.UUID],
    current_user: models.User,
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
        .filter(
            models.CalcScenario.flowsheet_version_id.in_(flowsheet_version_ids),
            models.CalcScenario.project_id == project.id,
        )
        .scalar()
        or 0
    )

    calc_runs_total = (
        db.query(func.count(models.CalcRun.id))
        .filter(
            models.CalcRun.flowsheet_version_id.in_(flowsheet_version_ids),
            models.CalcRun.project_id == project.id,
        )
        .scalar()
        or 0
    )

    status_rows = (
        db.query(models.CalcRun.status, func.count(models.CalcRun.id))
        .filter(
            models.CalcRun.flowsheet_version_id.in_(flowsheet_version_ids),
            models.CalcRun.project_id == project.id,
        )
        .group_by(models.CalcRun.status)
        .all()
    )
    calc_runs_by_status = {status: count for status, count in status_rows if status is not None}

    scenario_ids = [
        row[0]
        for row in db.query(models.CalcScenario.id)
        .filter(
            models.CalcScenario.flowsheet_version_id.in_(flowsheet_version_ids),
            models.CalcScenario.project_id == project.id,
        )
        .all()
    ]
    run_ids = [
        row[0]
        for row in db.query(models.CalcRun.id)
        .filter(
            models.CalcRun.flowsheet_version_id.in_(flowsheet_version_ids),
            models.CalcRun.project_id == project.id,
        )
        .all()
    ]

    scenario_last = (
        db.query(func.max(models.CalcScenario.created_at))
        .filter(models.CalcScenario.id.in_(scenario_ids))
        .scalar()
        if scenario_ids
        else None
    )
    run_last = (
        db.query(func.max(models.CalcRun.started_at))
        .filter(models.CalcRun.id.in_(run_ids))
        .scalar()
        if run_ids
        else None
    )

    comments_total = (
        db.query(func.count(models.Comment.id))
        .filter(models.Comment.project_id == project.id)
        .scalar()
        or 0
    )
    comment_last = (
        db.query(func.max(models.Comment.created_at))
        .filter(models.Comment.project_id == project.id)
        .scalar()
    )

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
    project_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> ProjectSummary:
    project = _ensure_project_exists_and_get(db, project_id)
    links = (
        db.query(models.ProjectFlowsheetVersion)
        .filter(models.ProjectFlowsheetVersion.project_id == project.id)
        .all()
    )
    flowsheet_version_ids = [link.flowsheet_version_id for link in links]
    return _calculate_project_summary(db, project, flowsheet_version_ids, current_user)


@router.get("/{project_id}/members", response_model=list[ProjectMemberRead])
def list_project_members(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> list[ProjectMemberRead]:
    project = _ensure_project_exists_and_get(db, project_id)
    _check_project_read_access(db, project, current_user)

    memberships = (
        db.query(models.ProjectMember).filter(models.ProjectMember.project_id == project.id).all()
    )
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


@router.post(
    "/{project_id}/members", response_model=ProjectMemberRead, status_code=status.HTTP_201_CREATED
)
def add_project_member(
    project_id: str,
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="User is already the project owner"
        )

    existing = (
        db.query(models.ProjectMember)
        .filter(
            models.ProjectMember.project_id == project.id, models.ProjectMember.user_id == user.id
        )
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
    project_id: str,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project = _ensure_project_exists_and_get(db, project_id)
    if project.owner_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    membership = (
        db.query(models.ProjectMember)
        .filter(
            models.ProjectMember.project_id == project.id, models.ProjectMember.user_id == user_id
        )
        .first()
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project member not found"
        )

    db.delete(membership)
    db.commit()
    return None


RECENT_RUNS_LIMIT = 10
RECENT_COMMENTS_LIMIT = 10


@router.get("/{project_id}/dashboard", response_model=ProjectDashboardResponse)
def get_project_dashboard(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> ProjectDashboardResponse:
    project = _ensure_project_exists_and_get(db, project_id)
    if current_user is None and project.owner_user_id is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Login required")

    # Get project flowsheet version links
    links = (
        db.query(models.ProjectFlowsheetVersion)
        .filter(models.ProjectFlowsheetVersion.project_id == project.id)
        .all()
    )
    flowsheet_version_ids = [link.flowsheet_version_id for link in links]
    summary = _calculate_project_summary(db, project, flowsheet_version_ids, current_user)
    _check_project_read_access(db, project, current_user)

    # Get flowsheet versions from already-loaded links (no additional query needed)
    flowsheet_versions_dto = [
        FlowsheetVersionRead.model_validate(link.flowsheet_version, from_attributes=True)
        for link in links
    ]

    if flowsheet_version_ids:
        scenarios = (
            db.query(models.CalcScenario)
            .filter(
                models.CalcScenario.flowsheet_version_id.in_(flowsheet_version_ids),
                models.CalcScenario.project_id == project.id,
            )
            .all()
        )
    else:
        scenarios = []
    scenarios_dto = [CalcScenarioRead.model_validate(s, from_attributes=True) for s in scenarios]

    if flowsheet_version_ids:
        recent_runs = (
            db.query(models.CalcRun)
            .filter(
                models.CalcRun.flowsheet_version_id.in_(flowsheet_version_ids),
                models.CalcRun.project_id == project.id,
            )
            .order_by(models.CalcRun.started_at.desc().nullslast())
            .limit(RECENT_RUNS_LIMIT)
            .all()
        )
    else:
        recent_runs = []
    recent_runs_dto = [CalcRunListItem.model_validate(r, from_attributes=True) for r in recent_runs]

    recent_comments = (
        db.query(models.Comment)
        .filter(models.Comment.project_id == project.id)
        .order_by(models.Comment.created_at.desc(), models.Comment.id.desc())
        .limit(RECENT_COMMENTS_LIMIT)
        .all()
    )
    recent_comments_dto = [
        CommentRead.model_validate(c, from_attributes=True) for c in recent_comments
    ]

    return ProjectDashboardResponse(
        project=ProjectRead.model_validate(project, from_attributes=True),
        summary=summary,
        flowsheet_versions=flowsheet_versions_dto,
        scenarios=scenarios_dto,
        recent_calc_runs=recent_runs_dto,
        recent_comments=recent_comments_dto,
    )
