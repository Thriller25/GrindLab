import uuid
from typing import Optional

from app import models
from app.db import get_db
from app.schemas import (
    CalcComparisonRead,
    CalcRunRead,
    CalcScenarioListItem,
    CalcScenarioRead,
    CommentRead,
    FlowsheetRead,
    FlowsheetVersionCloneRequest,
    FlowsheetVersionCloneResponse,
    FlowsheetVersionCreate,
    FlowsheetVersionExportBundle,
    FlowsheetVersionOverviewResponse,
    FlowsheetVersionRead,
    FlowsheetVersionUpdate,
    PaginatedResponse,
    PlantRead,
    ScenarioWithLatestRun,
    UnitRead,
)
from app.schemas.calc_io import CalcResultSummary
from app.schemas.flowsheet_kpi import (
    FlowsheetVersionKpiSummaryResponse,
    KpiAggregate,
    ScenarioKpiSummary,
)
from app.services.calc_service import get_flowsheet_version_or_404
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[FlowsheetVersionRead])
def list_flowsheet_versions(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    query = db.query(models.FlowsheetVersion)
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return PaginatedResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{version_id}", response_model=FlowsheetVersionRead)
def get_flowsheet_version(version_id: uuid.UUID, db: Session = Depends(get_db)):
    obj = db.query(models.FlowsheetVersion).get(version_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Flowsheet version not found"
        )
    return obj


@router.post("/", response_model=FlowsheetVersionRead, status_code=status.HTTP_201_CREATED)
def create_flowsheet_version(payload: FlowsheetVersionCreate, db: Session = Depends(get_db)):
    obj = models.FlowsheetVersion(**payload.dict())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{version_id}", response_model=FlowsheetVersionRead)
def update_flowsheet_version(
    version_id: uuid.UUID, payload: FlowsheetVersionUpdate, db: Session = Depends(get_db)
):
    obj = db.query(models.FlowsheetVersion).get(version_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Flowsheet version not found"
        )
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{version_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_flowsheet_version(version_id: uuid.UUID, db: Session = Depends(get_db)):
    obj = db.query(models.FlowsheetVersion).get(version_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Flowsheet version not found"
        )
    obj.is_active = False
    db.commit()
    return None


@router.post(
    "/{version_id}/clone",
    response_model=FlowsheetVersionCloneResponse,
    status_code=status.HTTP_201_CREATED,
)
def clone_flowsheet_version(
    version_id: uuid.UUID,
    payload: FlowsheetVersionCloneRequest,
    db: Session = Depends(get_db),
) -> FlowsheetVersionCloneResponse:
    source_version = get_flowsheet_version_or_404(db, version_id)
    new_label = payload.new_version_name or f"{source_version.version_label} (copy)"

    cloned_version = models.FlowsheetVersion(
        flowsheet_id=source_version.flowsheet_id,
        version_label=new_label,
        status=source_version.status,
        is_active=source_version.is_active,
        comment=source_version.comment,
        created_by=source_version.created_by,
    )
    db.add(cloned_version)
    db.commit()
    db.refresh(cloned_version)

    source_links = (
        db.query(models.ProjectFlowsheetVersion)
        .filter(models.ProjectFlowsheetVersion.flowsheet_version_id == version_id)
        .all()
    )
    for link in source_links:
        db.add(
            models.ProjectFlowsheetVersion(
                project_id=link.project_id,
                flowsheet_version_id=cloned_version.id,
            )
        )
    if source_links:
        db.commit()
        db.refresh(cloned_version)

    cloned_scenarios: list[CalcScenarioRead] = []
    if payload.clone_scenarios:
        source_scenarios = (
            db.query(models.CalcScenario)
            .filter(models.CalcScenario.flowsheet_version_id == version_id)
            .all()
        )
        for scenario in source_scenarios:
            cloned = models.CalcScenario(
                flowsheet_version_id=cloned_version.id,
                project_id=scenario.project_id,
                name=scenario.name,
                description=scenario.description,
                default_input_json=scenario.default_input_json,
                is_baseline=scenario.is_baseline,
                is_recommended=scenario.is_recommended,
                recommendation_note=scenario.recommendation_note,
                recommended_at=scenario.recommended_at,
            )
            if scenario.is_baseline:
                (
                    db.query(models.CalcScenario)
                    .filter(models.CalcScenario.project_id == scenario.project_id)
                    .update({models.CalcScenario.is_baseline: False}, synchronize_session=False)
                )
            db.add(cloned)
            cloned_scenarios.append(cloned)
        db.commit()
        for scenario in cloned_scenarios:
            db.refresh(scenario)

    return FlowsheetVersionCloneResponse(
        flowsheet_version=FlowsheetVersionRead.model_validate(cloned_version, from_attributes=True),
        scenarios=[
            CalcScenarioRead.model_validate(s, from_attributes=True) for s in cloned_scenarios
        ],
    )


@router.get("/{version_id}/overview", response_model=FlowsheetVersionOverviewResponse)
def get_flowsheet_version_overview(
    version_id: uuid.UUID,
    status: Optional[str] = Query("success", description="Status filter for latest scenario runs"),
    db: Session = Depends(get_db),
) -> FlowsheetVersionOverviewResponse:
    flowsheet_version = get_flowsheet_version_or_404(db, version_id)

    scenarios = (
        db.query(models.CalcScenario)
        .filter(models.CalcScenario.flowsheet_version_id == version_id)
        .order_by(models.CalcScenario.created_at.desc())
        .all()
    )

    scenario_items: list[ScenarioWithLatestRun] = []
    for scenario in scenarios:
        run_query = db.query(models.CalcRun).filter(models.CalcRun.scenario_id == scenario.id)
        if status is not None:
            run_query = run_query.filter(models.CalcRun.status == status)

        latest_run = (
            run_query.order_by(models.CalcRun.started_at.desc().nullslast()).limit(1).first()
        )

        scenario_items.append(
            ScenarioWithLatestRun(
                scenario=CalcScenarioListItem.model_validate(scenario, from_attributes=True),
                latest_run=(
                    CalcRunRead.model_validate(latest_run, from_attributes=True)
                    if latest_run
                    else None
                ),
            )
        )

    return FlowsheetVersionOverviewResponse(
        flowsheet_version=FlowsheetVersionRead.model_validate(
            flowsheet_version, from_attributes=True
        ),
        scenarios=scenario_items,
    )


@router.get("/{version_id}/export", response_model=FlowsheetVersionExportBundle)
def export_flowsheet_version_bundle(
    version_id: uuid.UUID, db: Session = Depends(get_db)
) -> FlowsheetVersionExportBundle:
    flowsheet_version = get_flowsheet_version_or_404(db, version_id)
    flowsheet = db.get(models.Flowsheet, flowsheet_version.flowsheet_id)
    plant = db.get(models.Plant, flowsheet.plant_id) if flowsheet else None

    if plant is None or flowsheet is None:
        raise HTTPException(status_code=404, detail="Related Plant or Flowsheet not found")

    units = db.query(models.Unit).filter(models.Unit.flowsheet_version_id == version_id).all()
    scenarios = (
        db.query(models.CalcScenario)
        .filter(models.CalcScenario.flowsheet_version_id == version_id)
        .order_by(models.CalcScenario.created_at.desc())
        .all()
    )
    runs = (
        db.query(models.CalcRun)
        .filter(models.CalcRun.flowsheet_version_id == version_id)
        .order_by(models.CalcRun.started_at.desc().nullslast())
        .all()
    )
    comparisons = (
        db.query(models.CalcComparison)
        .filter(models.CalcComparison.flowsheet_version_id == version_id)
        .order_by(models.CalcComparison.created_at.desc())
        .all()
    )
    scenario_ids = [scenario.id for scenario in scenarios]
    run_ids = [run.id for run in runs]
    comments: list[models.Comment] = []
    if scenario_ids or run_ids:
        comment_query = db.query(models.Comment)
        if scenario_ids and run_ids:
            comment_query = comment_query.filter(
                (models.Comment.scenario_id.in_(scenario_ids))
                | (models.Comment.calc_run_id.in_(run_ids))
            )
        elif scenario_ids:
            comment_query = comment_query.filter(models.Comment.scenario_id.in_(scenario_ids))
        else:
            comment_query = comment_query.filter(models.Comment.calc_run_id.in_(run_ids))
        comments = comment_query.order_by(models.Comment.created_at.desc()).all()

    return FlowsheetVersionExportBundle(
        plant=PlantRead.model_validate(plant, from_attributes=True),
        flowsheet=FlowsheetRead.model_validate(flowsheet, from_attributes=True),
        flowsheet_version=FlowsheetVersionRead.model_validate(
            flowsheet_version, from_attributes=True
        ),
        units=[UnitRead.model_validate(unit, from_attributes=True) for unit in units],
        scenarios=[CalcScenarioRead.model_validate(s, from_attributes=True) for s in scenarios],
        runs=[CalcRunRead.model_validate(r, from_attributes=True) for r in runs],
        comparisons=[
            CalcComparisonRead.model_validate(c, from_attributes=True) for c in comparisons
        ],
        comments=[CommentRead.model_validate(c, from_attributes=True) for c in comments],
    )


def _aggregate_kpis(runs: list[models.CalcRun]) -> KpiAggregate:
    summaries = []
    for run in runs:
        if run.result_json is None:
            continue
        try:
            summary = CalcResultSummary.model_validate(run.result_json)
            summaries.append(summary)
        except Exception:
            continue

    if not summaries:
        return KpiAggregate(count_runs=0)

    def _values(attr: str) -> list[float]:
        vals = []
        for summary in summaries:
            value = getattr(summary, attr)
            if value is not None:
                vals.append(value)
        return vals

    throughput_values = _values("throughput_tph")
    energy_values = _values("specific_energy_kwh_per_t")
    p80_values = _values("p80_out_microns")

    def _avg(values: list[float]) -> Optional[float]:
        return sum(values) / len(values) if values else None

    return KpiAggregate(
        count_runs=len(summaries),
        throughput_tph_min=min(throughput_values) if throughput_values else None,
        throughput_tph_max=max(throughput_values) if throughput_values else None,
        throughput_tph_avg=_avg(throughput_values),
        specific_energy_kwh_per_t_min=min(energy_values) if energy_values else None,
        specific_energy_kwh_per_t_max=max(energy_values) if energy_values else None,
        specific_energy_kwh_per_t_avg=_avg(energy_values),
        p80_out_microns_min=min(p80_values) if p80_values else None,
        p80_out_microns_max=max(p80_values) if p80_values else None,
        p80_out_microns_avg=_avg(p80_values),
    )


@router.get("/{version_id}/kpi-summary", response_model=FlowsheetVersionKpiSummaryResponse)
def get_flowsheet_version_kpi_summary(
    version_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> FlowsheetVersionKpiSummaryResponse:
    flowsheet_version = get_flowsheet_version_or_404(db, version_id)

    runs = (
        db.query(models.CalcRun)
        .filter(
            models.CalcRun.flowsheet_version_id == version_id,
            models.CalcRun.status == "success",
        )
        .all()
    )

    totals_kpi = _aggregate_kpis(runs)

    scenarios = (
        db.query(models.CalcScenario)
        .filter(models.CalcScenario.flowsheet_version_id == version_id)
        .all()
    )
    scenario_by_id = {s.id: s for s in scenarios}

    scenario_runs_map: dict[uuid.UUID, list[models.CalcRun]] = {s.id: [] for s in scenarios}
    for run in runs:
        if run.scenario_id and run.scenario_id in scenario_runs_map:
            scenario_runs_map[run.scenario_id].append(run)

    by_scenario: list[ScenarioKpiSummary] = []
    for scenario_id, scenario_runs in scenario_runs_map.items():
        scenario = scenario_by_id[scenario_id]
        kpi = _aggregate_kpis(scenario_runs)
        by_scenario.append(
            ScenarioKpiSummary(
                scenario_id=scenario.id,
                scenario_name=scenario.name,
                is_baseline=scenario.is_baseline,
                kpi=kpi,
            )
        )

    return FlowsheetVersionKpiSummaryResponse(
        flowsheet_version_id=flowsheet_version.id,
        totals=totals_kpi,
        by_scenario=by_scenario,
    )
