from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


class KpiAggregate(BaseModel):
    count_runs: int
    throughput_tph_min: Optional[float] = None
    throughput_tph_max: Optional[float] = None
    throughput_tph_avg: Optional[float] = None

    specific_energy_kwh_per_t_min: Optional[float] = None
    specific_energy_kwh_per_t_max: Optional[float] = None
    specific_energy_kwh_per_t_avg: Optional[float] = None

    p80_out_microns_min: Optional[float] = None
    p80_out_microns_max: Optional[float] = None
    p80_out_microns_avg: Optional[float] = None


class ScenarioKpiSummary(BaseModel):
    scenario_id: UUID
    scenario_name: str
    is_baseline: bool
    kpi: KpiAggregate


class FlowsheetVersionKpiSummaryResponse(BaseModel):
    flowsheet_version_id: UUID
    totals: KpiAggregate
    by_scenario: List[ScenarioKpiSummary]
