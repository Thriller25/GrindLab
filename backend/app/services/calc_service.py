import logging
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models
from app.schemas.calc_run import CalcRunCreate, CalcRunRead

logger = logging.getLogger(__name__)


class CalculationError(Exception):
    """Raised for predictable calculation/validation errors."""


def get_flowsheet_version_or_404(db: Session, flowsheet_version_id):
    """
    Fetch FlowsheetVersion by primary key or raise 404.
    """
    instance = db.get(models.FlowsheetVersion, flowsheet_version_id)
    if instance is None:
        raise HTTPException(status_code=404, detail=f"FlowsheetVersion {flowsheet_version_id} not found")
    return instance


def validate_input_json(input_json: Any) -> Dict[str, float]:
    if input_json is None or not isinstance(input_json, dict):
        raise CalculationError("input_json is required and must be an object")

    required_keys = ("feed_tph", "target_p80_microns")
    for key in required_keys:
        if key not in input_json:
            raise CalculationError("input_json must contain numeric fields 'feed_tph' and 'target_p80_microns'")

    try:
        feed_tph = float(input_json["feed_tph"])
        target_p80_microns = float(input_json["target_p80_microns"])
    except (TypeError, ValueError):
        raise CalculationError("input_json must contain numeric fields 'feed_tph' and 'target_p80_microns'")

    if feed_tph <= 0 or target_p80_microns <= 0:
        raise CalculationError("input_json must contain numeric fields 'feed_tph' and 'target_p80_microns'")

    return {"feed_tph": feed_tph, "target_p80_microns": target_p80_microns}


def run_flowsheet_calculation(db: Session, payload: CalcRunCreate) -> CalcRunRead:
    """
    MVP calculation: persist CalcRun, mock result JSON, and update status.
    """
    get_flowsheet_version_or_404(db, payload.flowsheet_version_id)
    validated_input = validate_input_json(payload.input_json)

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
                "throughput_tph": validated_input["feed_tph"],
                "p80_microns": validated_input["target_p80_microns"],
            },
        }

        calc_run.status = "success"
        calc_run.result_json = result_json
    except CalculationError:
        calc_run.status = "failed"
        calc_run.result_json = {"error": "Calculation validation failed"}
        raise
    except Exception as exc:  # pragma: no cover - unexpected error branch
        calc_run.status = "failed"
        calc_run.result_json = {"error": str(exc)}
        logger.exception("Unexpected calculation error")
        raise
    finally:
        calc_run.finished_at = datetime.now(timezone.utc)
        db.add(calc_run)
        db.commit()
        db.refresh(calc_run)

    return CalcRunRead.model_validate(calc_run, from_attributes=True)
