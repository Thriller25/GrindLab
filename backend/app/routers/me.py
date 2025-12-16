import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.routers.auth import ANONYMOUS_EMAIL, ANONYMOUS_ID, get_current_user_optional

router = APIRouter(prefix="/api/me", tags=["me"])


def _safe_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except Exception:
        return None


@router.get("/dashboard")
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
):
    """
    Dashboard endpoint for the current user.
    When unauthenticated, returns anonymous user info and demo/empty data.
    """
    is_anonymous = current_user is None or getattr(current_user, "id", None) == ANONYMOUS_ID
    user_email = getattr(current_user, "email", ANONYMOUS_EMAIL)
    user_id = getattr(current_user, "id", ANONYMOUS_ID)
    user_full_name = getattr(current_user, "full_name", "Anonymous")

    def _filter_owned(query):
        if hasattr(models.CalcRun, "started_by_user_id") and not is_anonymous:
            return query.filter(models.CalcRun.started_by_user_id == user_id)
        return query

    scenarios_total = 0
    if hasattr(models.CalcScenario, "created_by_user_id") and not is_anonymous:
        scenarios_total = (
            db.query(func.count(models.CalcScenario.id))
            .filter(models.CalcScenario.created_by_user_id == user_id)
            .scalar()
        ) or 0

    calc_runs_total = (
        _filter_owned(db.query(func.count(models.CalcRun.id))).scalar()  # type: ignore[arg-type]
        or 0
    )

    status_rows = (
        _filter_owned(db.query(models.CalcRun.status, func.count(models.CalcRun.id)))
        .group_by(models.CalcRun.status)
        .all()
    )
    calc_runs_by_status: Dict[str, int] = {status: count for status, count in status_rows if status is not None}

    recent_runs_query = _filter_owned(db.query(models.CalcRun))
    recent_runs = (
        recent_runs_query.order_by(models.CalcRun.started_at.desc().nullslast())  # type: ignore[union-attr]
        .limit(6)
        .all()
    )

    version_ids = [
        _safe_uuid(run.input_json.get("flowsheet_version_id"))  # type: ignore[arg-type]
        for run in recent_runs
        if isinstance(run.input_json, dict) and run.input_json.get("flowsheet_version_id")
    ]
    version_ids = [vid for vid in version_ids if vid]
    versions_map: Dict[uuid.UUID, models.FlowsheetVersion] = {}
    if version_ids:
        for v in db.query(models.FlowsheetVersion).filter(models.FlowsheetVersion.id.in_(version_ids)).all():
            versions_map[v.id] = v

    flowsheet_ids = list({v.flowsheet_id for v in versions_map.values()})
    flowsheets_map: Dict[uuid.UUID, models.Flowsheet] = {}
    if flowsheet_ids:
        for fs in db.query(models.Flowsheet).filter(models.Flowsheet.id.in_(flowsheet_ids)).all():
            flowsheets_map[fs.id] = fs

    plant_ids: List[uuid.UUID] = []
    for fs in flowsheets_map.values():
        if fs.plant_id not in plant_ids:
            plant_ids.append(fs.plant_id)
    plants_map: Dict[uuid.UUID, models.Plant] = {}
    if plant_ids:
        for p in db.query(models.Plant).filter(models.Plant.id.in_(plant_ids)).all():
            plants_map[p.id] = p

    def _extract_model_version(run: models.CalcRun) -> str:
        if isinstance(run.result_json, dict):
            mv = run.result_json.get("model_version")
            if mv:
                return str(mv)
        if isinstance(run.input_json, dict):
            mv = run.input_json.get("model_version")
            if mv:
                return str(mv)
        return "unknown"

    def _extract_kpi(run: models.CalcRun) -> Dict[str, Any]:
        if isinstance(run.result_json, dict):
            kpi = run.result_json.get("kpi") if isinstance(run.result_json, dict) else None
            if isinstance(kpi, dict):
                return {
                    "throughput_tph": kpi.get("throughput_tph"),
                    "product_p80_mm": kpi.get("product_p80_mm") or kpi.get("p80_out_microns"),
                    "specific_energy_kwhpt": kpi.get("specific_energy_kwh_per_t"),
                }
        return {}

    recent_runs_dto = []
    for run in recent_runs:
        input_json = run.input_json if isinstance(run.input_json, dict) else {}
        fv_id_raw = input_json.get("flowsheet_version_id")
        fv_id = _safe_uuid(fv_id_raw) if fv_id_raw else None
        fv = versions_map.get(fv_id) if fv_id else None
        fs = flowsheets_map.get(fv.flowsheet_id) if fv else None  # type: ignore[union-attr]
        plant = plants_map.get(fs.plant_id) if fs else None  # type: ignore[union-attr]
        baseline = None
        if isinstance(run.result_json, dict):
            baseline_obj = run.result_json.get("baseline_comparison")
            if isinstance(baseline_obj, dict):
                baseline = baseline_obj.get("baseline_run_id")
        is_baseline = bool(getattr(run.scenario, "is_baseline", False))

        dto = {
          "id": str(run.id),
          "model_version": _extract_model_version(run),
          "created_at": run.created_at.isoformat() if run.created_at else None,
          "plant_id": input_json.get("plant_id"),
          "plant_name": getattr(plant, "name", None),
          "flowsheet_version_id": fv_id_raw,
          "flowsheet_name": getattr(fs, "name", None),
          "scenario_name": run.scenario_name or input_json.get("scenario_name"),
          "comment": run.comment,
          **_extract_kpi(run),
          "baseline_run_id": baseline,
          "is_baseline": is_baseline,
        }
        recent_runs_dto.append(dto)

    all_runs_for_comments = _filter_owned(db.query(models.CalcRun)).all()
    comments_total = sum(
        1
        for run in all_runs_for_comments
        if _extract_model_version(run) == "grind_mvp_v1"
        and isinstance(run.comment, str)
        and run.comment.strip()
    )

    summary = {
        "calc_runs_total": calc_runs_total,
        "scenarios_total": scenarios_total,
        "comments_total": comments_total,
        "projects_total": 0,
        "calc_runs_by_status": calc_runs_by_status,
    }

    return {
        "user": {
            "id": str(user_id),
            "email": user_email,
            "full_name": user_full_name,
        },
        "summary": summary,
        "projects": [],
        "member_projects": [],
        "recent_calc_runs": recent_runs_dto,
        "recent_comments": [],
        "favorites": {"projects": [], "scenarios": [], "calc_runs": []},
    }
