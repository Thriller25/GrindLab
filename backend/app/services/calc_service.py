from sqlalchemy.orm import Session

from app import models
from ..schemas.calc import FlowsheetCalcRequest, FlowsheetCalcResult, UnitCalcResult


def run_flowsheet_calc(db: Session, payload: FlowsheetCalcRequest) -> FlowsheetCalcResult:
    """
    Very simple MVP calculation using deterministic mock values.
    """
    unit_results: list[UnitCalcResult] = []

    for unit in payload.units:
        unit_results.append(
            UnitCalcResult(
                unit_id=unit.unit_id,
                throughput_tph=unit.feed_rate_tph,
                specific_energy_kwh_per_t=10.0,
                p80_um=unit.target_p80_um or 200.0,
            )
        )

    total_throughput_tph = sum(unit.throughput_tph for unit in unit_results)
    total_energy_kwh_per_t = (
        sum(unit.specific_energy_kwh_per_t for unit in unit_results) / len(unit_results)
        if unit_results
        else 0.0
    )

    result = FlowsheetCalcResult(
        flowsheet_version_id=payload.flowsheet_version_id,
        total_throughput_tph=total_throughput_tph,
        total_energy_kwh_per_t=total_energy_kwh_per_t,
        units=unit_results,
    )

    payload_dict = payload.dict()
    result_dict = result.dict()

    calc_run = models.CalcRun(
        flowsheet_version_id=payload.flowsheet_version_id,
        request_json=payload_dict,
        result_json=result_dict,
    )
    db.add(calc_run)
    db.commit()

    return result
