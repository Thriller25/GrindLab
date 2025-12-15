from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from typing import Any

from app.schemas.calc_io import CalcInput, CalcResultSummary


class CalcRunCreate(BaseModel):
    flowsheet_version_id: UUID
    scenario_id: Optional[UUID] = None
    scenario_name: Optional[str] = None
    comment: Optional[str] = None
    input_json: Optional[CalcInput] = None


class CalcRunRead(BaseModel):
    id: UUID
    flowsheet_version_id: UUID
    scenario_id: Optional[UUID] = None
    scenario_name: Optional[str] = None
    is_baseline: Optional[bool] = None
    comment: Optional[str] = None
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error_message: Optional[str] = None
    input_json: Optional[CalcInput] = None
    result_json: Optional[Any] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CalcRunListItem(BaseModel):
    id: UUID
    flowsheet_version_id: UUID
    scenario_id: Optional[UUID] = None
    scenario_name: Optional[str] = None
    is_baseline: Optional[bool] = None
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    comment: Optional[str] = None
    error_message: Optional[str] = None
    input_json: Optional[CalcInput] = None
    result_json: Optional[Any] = None

    model_config = {"from_attributes": True}


class CalcRunListResponse(BaseModel):
    items: list[CalcRunListItem]
    total: int


class CalcRunCommentUpdate(BaseModel):
    comment: Optional[str] = Field(None, max_length=2000)


class CalcRunComparisonItem(BaseModel):
    id: UUID
    scenario_id: Optional[UUID] = None
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    input: CalcInput
    result: Optional[CalcResultSummary] = None


class CalcRunCompareResponse(BaseModel):
    items: list[CalcRunComparisonItem]
    total: int


class CalcRunDelta(BaseModel):
    throughput_delta_abs: Optional[float] = None
    throughput_delta_pct: Optional[float] = None
    specific_energy_delta_abs: Optional[float] = None
    specific_energy_delta_pct: Optional[float] = None
    p80_out_delta_abs: Optional[float] = None
    p80_out_delta_pct: Optional[float] = None


class CalcRunCompareWithBaselineItem(BaseModel):
    run: CalcRunComparisonItem
    deltas: CalcRunDelta


class CalcRunCompareWithBaselineResponse(BaseModel):
    baseline: CalcRunComparisonItem
    items: list[CalcRunCompareWithBaselineItem]
    total: int


class BaselineKpi(BaseModel):
    throughput_tph: Optional[float] = None
    product_p80_mm: Optional[float] = None
    specific_energy_kwhpt: Optional[float] = None
    circulating_load_percent: Optional[float] = None
    utilization_percent: Optional[float] = None


class CalcRunBaselineComparison(BaseModel):
    calc_run_id: UUID
    baseline_run_id: UUID
    current_kpi: BaselineKpi
    baseline_kpi: BaselineKpi
    delta: BaselineKpi

    @classmethod
    def from_results(
        cls,
        run_id: UUID,
        baseline_run_id: UUID,
        current_result,
        baseline_result,
    ) -> "CalcRunBaselineComparison":
        from app.schemas.grind_mvp import GrindMvpResult  # local import to avoid circular dependency

        def _to_kpi(result: GrindMvpResult) -> BaselineKpi:
            kpi = result.kpi
            return BaselineKpi(
                throughput_tph=kpi.throughput_tph,
                product_p80_mm=kpi.product_p80_mm,
                specific_energy_kwhpt=kpi.specific_energy_kwh_per_t,
                circulating_load_percent=kpi.circulating_load_percent,
                utilization_percent=kpi.mill_utilization_percent,
            )

        def _delta(current: Optional[float], baseline: Optional[float]) -> Optional[float]:
            if current is None or baseline is None:
                return None
            return current - baseline

        current_kpi = _to_kpi(current_result)
        baseline_kpi = _to_kpi(baseline_result)

        delta = BaselineKpi(
            throughput_tph=_delta(current_kpi.throughput_tph, baseline_kpi.throughput_tph),
            product_p80_mm=_delta(current_kpi.product_p80_mm, baseline_kpi.product_p80_mm),
            specific_energy_kwhpt=_delta(current_kpi.specific_energy_kwhpt, baseline_kpi.specific_energy_kwhpt),
            circulating_load_percent=_delta(
                current_kpi.circulating_load_percent, baseline_kpi.circulating_load_percent
            ),
            utilization_percent=_delta(current_kpi.utilization_percent, baseline_kpi.utilization_percent),
        )

        return cls(
            calc_run_id=run_id,
            baseline_run_id=baseline_run_id,
            current_kpi=current_kpi,
            baseline_kpi=baseline_kpi,
            delta=delta,
        )
