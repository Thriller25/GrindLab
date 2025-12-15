from typing import List, Optional, Tuple

from pydantic import BaseModel, Field

from app.schemas.calc_io import CalcResultSummary


class CalcResultStream(BaseModel):
    id: str
    name: Optional[str] = None
    mass_flow: Optional[float] = None
    size_distribution: List[Tuple[float, float]] = Field(default_factory=list, description="(size_um, cumulative_pass_pct)")
    is_feed: bool = False
    is_product: bool = False
    p80_um: Optional[float] = None
    p50_um: Optional[float] = None


class CalcResultUnit(BaseModel):
    id: str
    name: Optional[str] = None
    unit_type: Optional[str] = None
    input_stream_ids: List[str] = Field(default_factory=list)
    output_stream_ids: List[str] = Field(default_factory=list)
    throughput_tph: Optional[float] = None
    specific_energy_kwh_t: Optional[float] = None
    power_kw: Optional[float] = None


class CalcResultKPI(BaseModel):
    total_feed_tph: Optional[float] = None
    total_product_tph: Optional[float] = None
    mass_balance_error_pct: Optional[float] = None
    product_p80_um: Optional[float] = None
    product_p50_um: Optional[float] = None
    total_power_kw: Optional[float] = None
    specific_energy_kwh_t: Optional[float] = None


class CalcResult(CalcResultSummary):
    """
    Full calculation result payload stored in calc_run.result_json.

    Currently aligns with CalcResultSummary fields; extend here when
    result JSON grows (streams, units, detailed KPIs, etc.).
    """

    streams: List[CalcResultStream] = Field(default_factory=list)
    units: List[CalcResultUnit] = Field(default_factory=list)
    kpi: CalcResultKPI

    model_config = {"from_attributes": True}
