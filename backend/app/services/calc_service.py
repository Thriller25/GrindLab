import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models
from app.schemas.calc_run import CalcRunCreate, CalcRunRead

logger = logging.getLogger(__name__)


class CalculationError(Exception):
    """Raised for predictable calculation/validation errors."""


class CalcRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


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


def _persist_status(
    db: Session,
    calc_run: models.CalcRun,
    status: CalcRunStatus,
    finished_at: datetime | None = None,
    result_json: Dict[str, Any] | None = None,
    error_message: str | None = None,
) -> None:
    calc_run.status = status.value
    if finished_at:
        calc_run.finished_at = finished_at
    if result_json is not None:
        calc_run.result_json = result_json
    calc_run.error_message = error_message
    db.add(calc_run)
    db.commit()
    db.refresh(calc_run)


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
        status=CalcRunStatus.PENDING.value,
        started_at=started_at,
        input_json=payload.input_json,
        error_message=None,
    )
    db.add(calc_run)
    db.commit()
    db.refresh(calc_run)

    try:
        _persist_status(db, calc_run, CalcRunStatus.RUNNING)

        result_json: Dict[str, Any] = {
            "flowsheet_version_id": str(payload.flowsheet_version_id),
            "summary": {
                "throughput_tph": validated_input["feed_tph"],
                "p80_microns": validated_input["target_p80_microns"],
            },
        }

        _persist_status(
            db,
            calc_run,
            CalcRunStatus.SUCCESS,
            finished_at=datetime.now(timezone.utc),
            result_json=result_json,
            error_message=None,
        )
    except CalculationError as exc:
        _persist_status(
            db,
            calc_run,
            CalcRunStatus.FAILED,
            finished_at=datetime.now(timezone.utc),
            error_message=str(exc),
        )
        raise
    except Exception as exc:  # pragma: no cover - unexpected error branch
        _persist_status(
            db,
            calc_run,
            CalcRunStatus.FAILED,
            finished_at=datetime.now(timezone.utc),
            error_message="Internal calculation error",
        )
        logger.exception("Unexpected calculation error")
        raise

    return CalcRunRead.model_validate(calc_run, from_attributes=True)
