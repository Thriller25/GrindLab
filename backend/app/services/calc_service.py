from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy.orm import Session

from app import models
from app.schemas.calc_run import CalcRunCreate, CalcRunRead


def run_flowsheet_calculation(db: Session, payload: CalcRunCreate) -> CalcRunRead:
    """
    MVP calculation: persist CalcRun, mock result JSON, and update status.
    """
    started_at = datetime.now(timezone.utc)
    calc_run = models.CalcRun(
        flowsheet_version_id=payload.flowsheet_version_id,
        scenario_name=payload.scenario_name,
        comment=payload.comment,
        status="running",
        started_at=started_at,
        input_json=payload.input_json,
    )
    db.add(calc_run)
    db.commit()
    db.refresh(calc_run)

    try:
        result_json: Dict[str, Any] = {
            "flowsheet_version_id": str(payload.flowsheet_version_id),
            "summary": {
                "throughput_tph": 100.0,
                "p80_microns": 150.0,
            },
        }

        calc_run.status = "success"
        calc_run.result_json = result_json
    except Exception as exc:  # pragma: no cover - MVP error branch
        calc_run.status = "failed"
        calc_run.result_json = {"error": str(exc)}
    finally:
        calc_run.finished_at = datetime.now(timezone.utc)
        db.add(calc_run)
        db.commit()
        db.refresh(calc_run)

    return CalcRunRead.model_validate(calc_run, from_attributes=True)
