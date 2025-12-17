from __future__ import annotations

import uuid
from typing import Any, Dict, Iterable, Optional

from sqlalchemy.orm import Session

from app import models


def extract_model_version(run: models.CalcRun) -> Optional[str]:
    for source in (getattr(run, "result_json", None), getattr(run, "input_json", None)):
        if isinstance(source, dict):
            mv = source.get("model_version") or source.get("modelVersion")
            if mv:
                return str(mv)
    return None


def extract_kpi(run: models.CalcRun) -> Dict[str, Any]:
    result = getattr(run, "result_json", None)
    if not isinstance(result, dict):
        return {}
    kpi = result.get("kpi")
    return kpi if isinstance(kpi, dict) else {}


def is_grind_mvp_run(run: models.CalcRun) -> bool:
    mv = extract_model_version(run)
    return bool(mv and "grind_mvp" in mv)


def _sort_runs_by_kpi(runs: Iterable[models.CalcRun]) -> list[models.CalcRun]:
    def key(run: models.CalcRun):
        kpi = extract_kpi(run)
        throughput = kpi.get("throughput_tph") or kpi.get("throughput")
        created = getattr(run, "created_at", None)
        return (throughput or 0, created)

    return sorted(runs, key=key, reverse=True)


def find_best_project_run(
    db: Session, project_id: int, flowsheet_version_id: uuid.UUID
) -> Optional[models.CalcRun]:
    runs = (
        db.query(models.CalcRun)
        .filter(
            models.CalcRun.project_id == project_id,
            models.CalcRun.flowsheet_version_id == flowsheet_version_id,
            models.CalcRun.status == "success",
        )
        .all()
    )
    if not runs:
        return None
    return _sort_runs_by_kpi(runs)[0]


def find_baseline_run_for_version(
    db: Session, flowsheet_version_id: uuid.UUID
) -> Optional[models.CalcRun]:
    runs = (
        db.query(models.CalcRun)
        .join(models.CalcScenario, models.CalcScenario.id == models.CalcRun.scenario_id)
        .filter(
            models.CalcRun.flowsheet_version_id == flowsheet_version_id,
            models.CalcScenario.is_baseline.is_(True),
        )
        .order_by(models.CalcRun.started_at.desc().nullslast(), models.CalcRun.created_at.desc())
        .all()
    )
    return runs[0] if runs else None
