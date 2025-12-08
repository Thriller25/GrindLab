from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


class UnitCalcInput(BaseModel):
    unit_id: UUID
    feed_rate_tph: float
    ore_hardness: float
    target_p80_um: Optional[float] = None


class FlowsheetCalcRequest(BaseModel):
    flowsheet_version_id: UUID
    ore_density_t_per_m3: Optional[float] = None
    scenario_name: Optional[str] = None
    comment: Optional[str] = None
    units: List[UnitCalcInput]


class UnitCalcResult(BaseModel):
    unit_id: UUID
    throughput_tph: float
    specific_energy_kwh_per_t: float
    p80_um: float


class FlowsheetCalcResult(BaseModel):
    flowsheet_version_id: UUID
    total_throughput_tph: float
    total_energy_kwh_per_t: float
    units: List[UnitCalcResult]
