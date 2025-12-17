from typing import Optional

from pydantic import BaseModel


class CalcInput(BaseModel):
    feed_tph: Optional[float] = None
    target_p80_microns: Optional[float] = None
    ore_hardness_ab: Optional[float] = None
    ore_hardness_ta: Optional[float] = None
    water_fraction: Optional[float] = None


class CalcResultSummary(BaseModel):
    throughput_tph: Optional[float] = None
    specific_energy_kwh_per_t: Optional[float] = None
    p80_out_microns: Optional[float] = None
    circuit_efficiency_index: Optional[float] = None
