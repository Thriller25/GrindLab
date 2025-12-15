import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models
from app.schemas.calc_io import CalcInput
from app.schemas.calc_result import CalcResult, CalcResultKPI, CalcResultStream, CalcResultUnit
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


def get_calc_scenario_or_404(db: Session, scenario_id: uuid.UUID):
    """
    Fetch CalcScenario by primary key or raise 404.
    """
    scenario = db.get(models.CalcScenario, scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail=f"CalcScenario {scenario_id} not found")
    return scenario


def validate_input_json(input_json: Any) -> CalcInput:
    if input_json is None:
        raise CalculationError("input_json is required and must be an object")

    if isinstance(input_json, CalcInput):
        model = input_json
    elif isinstance(input_json, dict):
        try:
            model = CalcInput.model_validate(input_json)
        except Exception:
            raise CalculationError("input_json must contain numeric fields 'feed_tph' and 'target_p80_microns'")
    else:
        raise CalculationError("input_json is required and must be an object")

    if model.feed_tph <= 0 or model.target_p80_microns <= 0:
        raise CalculationError("input_json must contain numeric fields 'feed_tph' and 'target_p80_microns'")

    return model


def _interp_pXX_from_cumulative(curve: Sequence[Tuple[float, float]], target_pct: float) -> Optional[float]:
    """
    Linear interpolation of size (um) at given cumulative passing percent.
    curve: iterable of (size_um, cumulative_pass_pct) sorted by size.
    """
    if not curve:
        return None
    curve_sorted = sorted(curve, key=lambda x: x[0])
    if target_pct <= curve_sorted[0][1]:
        return curve_sorted[0][0]
    if target_pct >= curve_sorted[-1][1]:
        return curve_sorted[-1][0]
    for (x1, y1), (x2, y2) in zip(curve_sorted[:-1], curve_sorted[1:]):
        if (y1 <= target_pct <= y2) or (y2 <= target_pct <= y1):
            if y2 == y1:
                return x1
            ratio = (target_pct - y1) / (y2 - y1)
            return x1 + ratio * (x2 - x1)
    return curve_sorted[-1][0]


def _compute_stream_size_kpi(stream: CalcResultStream) -> CalcResultStream:
    if not stream.size_distribution:
        return stream
    p80 = _interp_pXX_from_cumulative(stream.size_distribution, 80.0)
    p50 = _interp_pXX_from_cumulative(stream.size_distribution, 50.0)
    stream.p80_um = p80
    stream.p50_um = p50
    return stream


def _compute_product_pxx(streams: Iterable[CalcResultStream], attr: str) -> Optional[float]:
    product_streams = [s for s in streams if s.is_product and getattr(s, attr) is not None and s.mass_flow]
    total_mass = sum(s.mass_flow for s in product_streams if s.mass_flow is not None)
    if not product_streams or total_mass == 0:
        return None
    return sum((getattr(s, attr) or 0.0) * (s.mass_flow or 0.0) for s in product_streams) / total_mass


def _compute_unit_throughput_tph(unit: CalcResultUnit, streams_by_id: dict[str, CalcResultStream]) -> Optional[float]:
    input_flows = [streams_by_id[sid] for sid in unit.input_stream_ids if sid in streams_by_id]
    if input_flows:
        return sum(s.mass_flow for s in input_flows if s.mass_flow is not None)
    output_flows = [streams_by_id[sid] for sid in unit.output_stream_ids if sid in streams_by_id]
    if output_flows:
        return sum(s.mass_flow for s in output_flows if s.mass_flow is not None)
    return None


def _compute_units_energy_kpi(
    units: list[CalcResultUnit],
    streams: list[CalcResultStream],
    default_specific_energy: Optional[float] = None,
) -> list[CalcResultUnit]:
    streams_by_id = {s.id: s for s in streams}
    updated: list[CalcResultUnit] = []
    for unit in units:
        throughput = _compute_unit_throughput_tph(unit, streams_by_id)
        specific_energy = unit.specific_energy_kwh_t if unit.specific_energy_kwh_t is not None else default_specific_energy
        power_kw = throughput * specific_energy if throughput is not None and specific_energy is not None else None
        unit.throughput_tph = throughput
        unit.specific_energy_kwh_t = specific_energy
        unit.power_kw = power_kw
        updated.append(unit)
    return updated


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
        scenario_id=payload.scenario_id,
        scenario_name=payload.scenario_name,
        comment=payload.comment,
        status=CalcRunStatus.PENDING.value,
        started_at=started_at,
        input_json=validated_input.model_dump(),
        error_message=None,
    )
    db.add(calc_run)
    db.commit()
    db.refresh(calc_run)

    try:
        _persist_status(db, calc_run, CalcRunStatus.RUNNING)

        throughput = validated_input.feed_tph
        p80_out = validated_input.target_p80_microns

        # Build simple synthetic streams to carry granulometry KPIs
        feed_stream = CalcResultStream(
            id="feed",
            name="Feed",
            mass_flow=validated_input.feed_tph,
            size_distribution=[
                (p80_out * 0.5, 40.0),
                (p80_out, 80.0),
                (p80_out * 1.5, 95.0),
            ],
            is_feed=True,
        )
        product_stream = CalcResultStream(
            id="product",
            name="Product",
            mass_flow=throughput,
            size_distribution=[
                (p80_out * 0.6, 50.0),
                (p80_out, 80.0),
                (p80_out * 1.2, 95.0),
            ],
            is_product=True,
        )
        streams = [_compute_stream_size_kpi(feed_stream), _compute_stream_size_kpi(product_stream)]

        units = [
            CalcResultUnit(
                id="unit-1",
                name="Comminution Stage",
                unit_type="MILL",
                input_stream_ids=[feed_stream.id],
                output_stream_ids=[product_stream.id],
                specific_energy_kwh_t=10.0,
            )
        ]
        units = _compute_units_energy_kpi(units, streams, default_specific_energy=10.0)
        total_power_kw = sum(u.power_kw for u in units if u.power_kw is not None)
        total_power_kw = total_power_kw if units else None
        total_product = throughput
        global_specific_energy = (
            total_power_kw / total_product if total_power_kw is not None and total_product else None
        )

        total_feed = validated_input.feed_tph
        mass_balance_error_pct = 0.0
        if total_feed:
            mass_balance_error_pct = 100.0 * (total_product - total_feed) / total_feed

        result_model = CalcResult(
            throughput_tph=throughput,
            specific_energy_kwh_per_t=10.0,
            p80_out_microns=p80_out,
            circuit_efficiency_index=0.95,
            kpi=CalcResultKPI(
                total_feed_tph=total_feed,
                total_product_tph=total_product,
                mass_balance_error_pct=mass_balance_error_pct,
                product_p80_um=_compute_product_pxx(streams, "p80_um"),
                product_p50_um=_compute_product_pxx(streams, "p50_um"),
                total_power_kw=total_power_kw,
                specific_energy_kwh_t=global_specific_energy,
            ),
            streams=streams,
            units=units,
        )
        result_json: Dict[str, Any] = result_model.model_dump()

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


def run_flowsheet_calculation_by_scenario(db: Session, scenario_id: uuid.UUID) -> CalcRunRead:
    """
    Run calculation using stored CalcScenario defaults.
    """
    scenario = get_calc_scenario_or_404(db, scenario_id)
    validated_input = validate_input_json(scenario.default_input_json)
    payload = CalcRunCreate(
        flowsheet_version_id=scenario.flowsheet_version_id,
        scenario_id=scenario.id,
        scenario_name=scenario.name,
        input_json=validated_input,
    )
    return run_flowsheet_calculation(db=db, payload=payload)
