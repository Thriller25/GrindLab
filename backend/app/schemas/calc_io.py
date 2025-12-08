from typing import Optional

from pydantic import BaseModel


class CalcInput(BaseModel):
    feed_tph: float
    target_p80_microns: float
    ore_hardness_ab: Optional[float] = None
    ore_hardness_ta: Optional[float] = None
    water_fraction: Optional[float] = None


class CalcResultSummary(BaseModel):
    throughput_tph: float
    specific_energy_kwh_per_t: float
    p80_out_microns: float
    circuit_efficiency_index: Optional[float] = None
